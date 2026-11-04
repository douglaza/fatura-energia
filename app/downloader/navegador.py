"""Navegação no portal CEMIG até a fatura e download do PDF.

Este é o "primeiro estágio" da automação: o PDF baixado aqui é o que,
depois, será enviado para ``POST /faturas/upload`` (ou alimentado direto
no parser) — fechando o ciclo portal → banco.

O fluxo é dividido em funções pequenas que recebem um ``page`` já aberto.
Isso mantém o código testável: nos testes, um objeto falso imita o
subconjunto da API do Playwright que usamos, sem abrir browser.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.downloader.config import CemigSettings, cemig_settings
from app.downloader.auth import SessionExpired, SessionManager, dispensar_cookies

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

#: Tempo máximo (ms) para cada espera de elemento/download no portal.
TIMEOUT_MS = 30_000

#: Timeout curto para tentativas opcionais (nova aba, busca por texto).
TIMEOUT_CURTO_MS = 5_000

#: Item do menu lateral que abre a lista de contas/faturas.
SELETOR_MENU_CONTAS = 'div[title="Navegar para Contas"]'

#: Card (clicável) que representa uma fatura na lista.
SELETOR_CARD = "div.clickable"

#: Marca dentro do card que identifica a fatura ainda não paga.
SELETOR_CARD_EM_ABERTO = 'span[title="Em aberto"]'

#: Botão "Baixar PDF" na página de detalhes da fatura.
#: Constante pública para que os testes possam registrá-la no dublê
#  (``FakePage(visiveis={..., navegador.SELETOR_BAIXAR_PDF})``).

SELETOR_BAIXAR_PDF = 'div.clickable:has(a:text-is("Baixar PDF"))'

SELETORES_BAIXAR_PDF = (
    SELETOR_BAIXAR_PDF,
    'a:text-is("Baixar PDF")',
    'button:has-text("Baixar PDF")',
    'text="Baixar PDF"',
)

#: Padrão de URL da página de detalhes (navegação na mesma aba).
URL_DETALHES = "**/bills/duplicate-bill/details**"

NOME_FALLBACK = "fatura_cemig.pdf"

MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

_PADRAO_MES_ANO = re.compile(
    r"^(?:(?P<mes>\d{1,2})/(?P<ano>\d{4})|(?P<ano_iso>\d{4})-(?P<mes_iso>\d{1,2}))$"
)


class FaturaNaoEncontrada(RuntimeError):
    """Nenhum card de fatura corresponde ao mês pedido."""


# --------------------------------------------------------------------------- #
# Mês de referência                                                            #
# --------------------------------------------------------------------------- #
def normalizar_mes_referencia(mes_ref: str) -> str:
    """Aceita ``9/2026``, ``09/2026`` ou ``2026-09`` e devolve sempre ``MM/AAAA``."""
    texto = (mes_ref or "").strip()
    m = _PADRAO_MES_ANO.match(texto)
    if not m:
        raise ValueError(
            f"Mês de referência inválido: {mes_ref!r} (esperado MM/AAAA)."
        )
    mes = int(m.group("mes") or m.group("mes_iso"))
    ano = m.group("ano") or m.group("ano_iso")
    if not 1 <= mes <= 12:
        raise ValueError(f"Mês inválido: {mes} (esperado 1..12) em {mes_ref!r}.")
    return f"{mes:02d}/{ano}"


def mes_por_extenso(mes_ref: str) -> str:
    """``'09/2026'`` → ``'Setembro 2026'`` (formato usado nos cards do portal)."""
    mes, ano = normalizar_mes_referencia(mes_ref).split("/")
    return f"{MESES[int(mes)]} {ano}"


# --------------------------------------------------------------------------- #
# Passos da navegação (cada um recebe a página já pronta)                      #
# --------------------------------------------------------------------------- #
def navegar_ate_faturas(page: Page, cfg: CemigSettings = cemig_settings) -> None:
    """Abre a página de faturas da área do cliente.

    Se o portal devolver o login, a sessão salva não vale mais — falhamos
    alto, em vez de seguir navegando como visitante.
    """
    logger.info("Abrindo %s", cfg.faturas_url)
    page.goto(cfg.faturas_url, wait_until="load")
    page.wait_for_timeout(2_000)  # a SPA monta o conteúdo depois do load

    if "login" in str(page.url).lower():
        raise SessionExpired(
            "O portal redirecionou para o login: a sessão salva expirou. "
            "Renove com python -m app.downloader --login."
        )
    dispensar_cookies(page)


def abrir_menu_contas(page: Page) -> None:
    """Clica no item do menu lateral que lista as contas/faturas."""
    menu = page.locator(SELETOR_MENU_CONTAS)
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    menu.click()
    logger.info("Menu 'Contas' aberto.")


def localizar_card(page: Page, mes_ref: str | None = None):
    """Devolve o card clicável da fatura a baixar.

    - Sem ``mes_ref``: escolhe a fatura **em aberto** (comportamento do
      projeto original).
    - Com ``mes_ref``: procura o card daquele mês, primeiro no formato
      ``MM/AAAA`` e depois por extenso (``Outubro 2026``).
    """
    if mes_ref is None:
        card = page.locator(SELETOR_CARD).filter(
            has=page.locator(SELETOR_CARD_EM_ABERTO)
        ).first
        card.wait_for(state="visible", timeout=TIMEOUT_MS)
        logger.info("Fatura em aberto localizada.")
        return card

    referencia = normalizar_mes_referencia(mes_ref)
    for texto in (referencia, mes_por_extenso(referencia)):
        card = page.locator(SELETOR_CARD).filter(has_text=texto).first
        try:
            card.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)
        except Exception:
            logger.debug("Nenhum card com o texto %r.", texto)
            continue
        logger.info("Fatura %s localizada pelo texto %r.", referencia, texto)
        return card

    raise FaturaNaoEncontrada(
        f"Nenhuma fatura encontrada para {referencia} na lista do portal. "
        "Confira se a fatura já foi emitida e se o mês está correto."
    )


def encontrar_botao_baixar(detalhes_page):
    ultimo_erro = None

    for seletor in SELETORES_BAIXAR_PDF:
        try:
            loc = detalhes_page.locator(seletor).first
            loc.wait_for(state="visible", timeout=TIMEOUT_CURTO_MS)

            logger.info(
                "Botão 'Baixar PDF' encontrado via seletor %r",
                seletor,
            )

            return loc

        except Exception as exc:
            ultimo_erro = exc

    raise RuntimeError(
        "Botão 'Baixar PDF' não encontrado na página."
    ) from ultimo_erro


def baixar_pdf_do_card(
    page: Page,
    card,
    destino_dir: Path,
    nome_fallback: str = NOME_FALLBACK,
) -> Path:
    """Clica no card, chega à página de detalhes, clica em 'Baixar PDF' e salva o PDF.

    O portal pode abrir os detalhes em nova aba ou navegar na mesma aba —
    lidamos com os dois casos. A aba extra, se aberta, é sempre fechada
    (mesmo em caso de erro).
    """
    destino_dir.mkdir(parents=True, exist_ok=True)

    # 1. Clica no card e descobre se abriu nova aba ou navegou na mesma
    detalhes_page: Page
    nova_aba = False
    try:
        with page.context.expect_page(timeout=TIMEOUT_CURTO_MS) as new_page_info:
            card.click()
        detalhes_page = new_page_info.value
        nova_aba = True
        
    except Exception:
        page.wait_for_timeout(3000)

        detalhes_page = page
        nova_aba = False

        print("URL atual:", page.url)
        logger.info("Detalhes abriram na mesma aba: %s", page.url)
    # with page.context.expect_page(timeout=TIMEOUT_CURTO_MS) as new_page_info:
    #     card.click()

    # try:
    #     detalhes_page = new_page_info.value
    #     nova_aba = True
    # except Exception:
    #     page.wait_for_url(URL_DETALHES, timeout=TIMEOUT_MS)
    #     detalhes_page = page


    # try:
    #     detalhes_page.wait_for_load_state()

    #     # 2. Localiza o botão "Baixar PDF" (div clicável que contém o link)
    #     baixar_link = detalhes_page.locator(SELETOR_BAIXAR_PDF).first
    #     baixar_link.wait_for(state="visible", timeout=TIMEOUT_MS)
    #     logger.info("Botão 'Baixar PDF' encontrado, clicando...")

    #     # 3. Captura o download ao clicar
    #     with detalhes_page.expect_download(timeout=TIMEOUT_MS) as download_info:
    #         baixar_link.click()

        detalhes_page.wait_for_load_state()

        botao = encontrar_botao_baixar(detalhes_page)

        with detalhes_page.expect_download(timeout=TIMEOUT_MS) as download_info:
            logger.info("Clicando em 'Baixar PDF'...")
            botao.click()


        download = download_info.value

        nome = getattr(download, "suggested_filename", None) or nome_fallback
        if not nome.lower().endswith(".pdf"):
            nome = f"{nome}.pdf"
        destino = destino_dir / nome

        download.save_as(destino)
        logger.info("Fatura salva em %s", destino)
        return destino
    finally:
        # Fecha apenas a aba que NÓS abrimos — nunca a página original.
        if nova_aba:
            try:
                detalhes_page.close()
            except Exception:
                logger.warning("Não foi possível fechar a aba de detalhes.")


# --------------------------------------------------------------------------- #
# Orquestração                                                                 #
# --------------------------------------------------------------------------- #
def navegar_e_baixar(
    page: Page,
    cfg: CemigSettings = cemig_settings,
    mes_ref: str | None = None,
) -> Path:
    """Executa o fluxo completo sobre uma página já autenticada."""
    navegar_ate_faturas(page, cfg)
    abrir_menu_contas(page)
    card = localizar_card(page, mes_ref)
    return baixar_pdf_do_card(
        page,
        card,
        cfg.download_dir,
        nome_fallback=(
            f"fatura_{normalizar_mes_referencia(mes_ref).replace('/', '-')}.pdf"
            if mes_ref
            else NOME_FALLBACK
        ),
    )

def baixar_fatura(
    mes_ref: str | None = None,
    *,
    headless: bool | None = None,
    cfg: CemigSettings = cemig_settings,
    session: SessionManager | None = None,
) -> Path:
    if mes_ref is not None:
        normalizar_mes_referencia(mes_ref)  # falha cedo, antes do browser

    session = session or SessionManager(cfg)
    session.ensure_valid()  # levanta SessionExpired se não há sessão válida

    headless = cfg.headless if headless is None else headless
    logger.info("Iniciando navegação (headless=%s, mes_ref=%s)", headless, mes_ref)

    with session.abrir_contexto(headless=headless) as page:
        return navegar_e_baixar(page, cfg, mes_ref)

    # normalizar_mes_referencia(mes_ref) # falha cedo, antes de abrir browser