"""Testes da automação de download (sem abrir browser).

Estratégia: as funções de navegação recebem um ``page`` já pronto, então os
testes usam um dublê (``FakePage``) que imita o subconjunto da API do
Playwright que o código utiliza. Nenhum Chromium é iniciado e ``playwright``
nem precisa estar instalado para a suíte rodar.
"""

from __future__ import annotations

import base64
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.downloader.config import CemigSettings

from app.downloader import auth, navegador
from app.downloader.auth import SessionExpired, SessionManager

SELETOR_BAIXAR_PDF = 'div.clickable:has(a:text-is("Baixar PDF"))'

# --------------------------------------------------------------------------- #
# Dublês do Playwright                                                         #
# --------------------------------------------------------------------------- #
class FakeTimeout(Exception):
    """Equivalente ao ``playwright.sync_api.TimeoutError``."""


class FakeDownload:
    def __init__(self, nome: str = "fatura.pdf"):
        self.suggested_filename = nome
        self.destino: Path | None = None

    def save_as(self, destino):
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"%PDF-1.4 conteudo falso")
        self.destino = destino


class FakeExpectDownload:
    def __init__(self, download: FakeDownload):
        self._download = download

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    @property
    def value(self):
        return self._download


class FakeLocator:
    def __init__(self, page, seletor, filtro_visivel=None, filtro_texto=None):
        self.page = page
        self.seletor = seletor
        self.filtro_visivel = filtro_visivel
        self.filtro_texto = filtro_texto

    @property
    def first(self):
        return self

    def filter(self, has=None, has_text=None):
        return FakeLocator(
            self.page,
            self.seletor,
            filtro_visivel=getattr(has, "seletor", None),
            filtro_texto=has_text,
        )

    def is_visible(self, timeout=None):
        return self.page.esta_visivel(
            self.seletor, self.filtro_visivel, self.filtro_texto
        )

    def wait_for(self, state="visible", timeout=None):
        if not self.is_visible():
            raise FakeTimeout(f"elemento {self.seletor!r} não apareceu")

    def click(self):
        self.page.cliques.append(self.seletor)

    def fill(self, valor):
        self.page.preenchidos.append((self.seletor, valor))


class FakeExpectPage:
    def __enter__(self):
        return self

    @property
    def value(self):
        raise FakeTimeout("nova aba não abre no fake")

    def __exit__(self, *args):
        return False


class FakePage:
    """Imita o subconjunto da API do Playwright usada em ``navegador``."""

    def __init__(
        self,
        visiveis=(),
        textos_cards=(),
        url_apos_goto: str | None = None,
        nome_download: str = "fatura.pdf",
        url_detalhes=None
    ):
        self.visiveis = set(visiveis)
        self.visiveis.add(
            navegador.SELETOR_BAIXAR_PDF
        )
        self.textos_cards = tuple(textos_cards)
        self.url_apos_goto = url_apos_goto
        self.url = ""
        self.download = FakeDownload(nome_download)
        self.gotos: list[tuple[str, str]] = []
        self.cliques: list[str] = []
        self.esperas_ms: list[int] = []
        self.preenchidos: list[tuple[str, str]] = []
        self.url_detalhes = url_detalhes
        self.context = FakeContext(self)
        self.fechada = False

    def esta_visivel(self, seletor, filtro_visivel=None, filtro_texto=None) -> bool:
        if seletor not in self.visiveis:
            return False
        if filtro_visivel is not None and filtro_visivel not in self.visiveis:
            return False
        if filtro_texto is not None:
            return any(filtro_texto in texto for texto in self.textos_cards)
        return True

    def goto(self, url, wait_until="load", **_kwargs):
        self.gotos.append((url, wait_until))
        self.url = self.url_apos_goto or url

    def wait_for_timeout(self, ms):
        self.esperas_ms.append(ms)

    def locator(self, seletor):
        return FakeLocator(self, seletor)

    def expect_download(self, timeout=None):
        return FakeExpectDownload(self.download)

    def wait_for_url(self, pattern, timeout=None):
        self.url = self.url_detalhes or self.url

    def wait_for_load_state(self, state="load", **_kwargs):
        pass
    
    def close(self): 
        self.fechada = True


class FakeSession:
    """Sessão de mentira: registra as chamadas em vez de abrir browser."""

    def __init__(self, page: FakePage | None = None, valida: bool = True, url_detalhes: str | None = None):
        self.page = page or FakePage(
            visiveis={
                navegador.SELETOR_MENU_CONTAS,
                navegador.SELETOR_CARD,
                navegador.SELETOR_CARD_EM_ABERTO,
            }
        )
        self.valida = valida
        self.ensure_chamado = False
        self.contexto_aberto = False
        self.headless_usado: bool | None = None
        self.url_detalhes = url_detalhes

    def ensure_valid(self) -> None:
        self.ensure_chamado = True
        if not self.valida:
            raise SessionExpired("sessão expirada (dublê)")

    @contextmanager
    def abrir_contexto(self, headless: bool = True):
        self.contexto_aberto = True
        self.headless_usado = headless
        yield self.page


class FakeContext:
    def __init__(self, page):
        self.page = page

    def expect_page(self, timeout=None):
        return FakeExpectPage()

# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def cfg(tmp_path: Path) -> CemigSettings:
    """Configuração isolada em diretório temporário (ignora o .env real)."""
    return CemigSettings(
        _env_file=None,
        download_dir=tmp_path / "raw",
        faturas_url="https://atende.cemig.com.br/portal/cliente/faturas",
        state_file=tmp_path / "session_state.json"
    )
    

# --- [PERSISTÊNCIA] helpers dos testes de sessão salva (a reativar) ---------
def _jwt(exp: datetime, sub: str = "123") -> str:
    """Monta um JWT sintético (assinatura falsa) com a claim ``exp``."""

    def b64(dados: dict) -> str:
        bruto = json.dumps(dados).encode()
        return base64.urlsafe_b64encode(bruto).rstrip(b"=").decode()

    header = b64({"alg": "HS256", "typ": "JWT"})
    payload = b64({"exp": int(exp.timestamp()), "sub": sub})
    return f"{header}.{payload}.fake"


def _salvar_estado(cfg: CemigSettings, cookies: list[dict]) -> None:
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(
        json.dumps({"cookies": cookies, "origins": []}), encoding="utf-8"
    )


def _cookie_token(token: str) -> dict:
    return {
        "name": auth.TOKEN_COOKIE,
        "value": token,
        "domain": ".cemig.com.br",
        "path": "/",
    }


# --------------------------------------------------------------------------- #
# Mês de referência                                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("10/2026", "10/2026"), ("9/2026", "09/2026"), ("2026-09", "09/2026"),
     (" 12/2025 ", "12/2025")],
)
def test_normalizar_mes_referencia_aceita_formatos(entrada, esperado):
    assert navegador.normalizar_mes_referencia(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "13/2026", "00/2026", "outubro", "10-2026", "2026"])
def test_normalizar_mes_referencia_rejeita_formatos_invalidos(entrada):
    with pytest.raises(ValueError):
        navegador.normalizar_mes_referencia(entrada)


def test_mes_por_extenso():
    assert navegador.mes_por_extenso("10/2026") == "Outubro 2026"
    assert navegador.mes_por_extenso("2026-03") == "Março 2026"


# --------------------------------------------------------------------------- #
# JWT                                                                         #
# --------------------------------------------------------------------------- #
def test_decodificar_jwt_le_claims():
    token = _jwt(datetime.now(timezone.utc) + timedelta(hours=1), sub="abc")
    claims = auth.decodificar_jwt(token)
    assert claims["sub"] == "abc"
    assert "exp" in claims


def test_decodificar_jwt_malformado_levanta_session_expired():
    with pytest.raises(SessionExpired):
        auth.decodificar_jwt("sem-dois-pontos")
    with pytest.raises(SessionExpired):
        auth.decodificar_jwt("aaa.###.ccc")


def test_expiracao_do_token():
    exp = datetime.now(timezone.utc) + timedelta(minutes=42)
    resultado = auth.expiracao_do_token(_jwt(exp))
    assert resultado is not None
    assert abs((resultado - exp).total_seconds()) < 1

    assert auth.expiracao_do_token("aaa.bbb.ccc") is None  # payload inválido


# --------------------------------------------------------------------------- #
# Validação da sessão salva                                                   #
# --------------------------------------------------------------------------- #
def test_sessao_invalida_sem_arquivo_de_estado(cfg):
    assert SessionManager(cfg).is_session_valid() is False
    assert SessionManager(cfg).token_expiry() is None


def test_sessao_valida_com_token_futuro(cfg):
    exp = datetime.now(timezone.utc) + timedelta(hours=2)
    _salvar_estado(cfg, [_cookie_token(_jwt(exp))])

    gerenciador = SessionManager(cfg)
    assert gerenciador.is_session_valid() is True
    assert gerenciador.token_expiry() is not None


def test_sessao_expirada_com_token_no_passado(cfg):
    exp = datetime.now(timezone.utc) - timedelta(minutes=1)
    _salvar_estado(cfg, [_cookie_token(_jwt(exp))])
    assert SessionManager(cfg).is_session_valid() is False


def test_sessao_invalida_dentro_da_margem_de_seguranca(cfg):
    """Token que expira em 5 min é considerado inválido (margem padrão 15 min)."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    _salvar_estado(cfg, [_cookie_token(_jwt(exp))])
    assert SessionManager(cfg).is_session_valid() is False


def test_sessao_invalida_sem_cookie_de_token(cfg):
    _salvar_estado(cfg, [{"name": "outro-cookie", "value": "x"}])
    assert SessionManager(cfg).is_session_valid() is False


def test_estado_de_sessao_corrompido_e_tratado_como_expirado(cfg):
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text("{isso não é json", encoding="utf-8")
    assert SessionManager(cfg).is_session_valid() is False


# --------------------------------------------------------------------------- #
# Navegação até as faturas                                                    #
# --------------------------------------------------------------------------- #
def test_navegar_ate_faturas_abre_url_configurada(cfg):
    page = FakePage()
    navegador.navegar_ate_faturas(page, cfg)

    assert page.gotos == [(cfg.faturas_url, "load")]
    assert 2_000 in page.esperas_ms  # espera a SPA montar


def test_navegar_ate_faturas_com_redirect_para_login_levanta_erro(cfg):
    page = FakePage(url_apos_goto=f"{cfg.base_url}/portal/login")
    with pytest.raises(SessionExpired) as exc:
        navegador.navegar_ate_faturas(page, cfg)
    assert "--login" in str(exc.value)


def test_abrir_menu_contas_clica_no_menu_lateral():
    page = FakePage(visiveis={navegador.SELETOR_MENU_CONTAS})
    navegador.abrir_menu_contas(page)
    assert page.cliques == [navegador.SELETOR_MENU_CONTAS]


def test_abrir_menu_contas_sem_elemento_levanta_timeout():
    page = FakePage()  # nada visível
    with pytest.raises(FakeTimeout):
        navegador.abrir_menu_contas(page)


def test_localizar_card_sem_mes_usa_fatura_em_aberto():
    page = FakePage(
        visiveis={navegador.SELETOR_CARD, navegador.SELETOR_CARD_EM_ABERTO}
    )
    card = navegador.localizar_card(page)
    assert card.seletor == navegador.SELETOR_CARD
    assert card.filtro_visivel == navegador.SELETOR_CARD_EM_ABERTO


def test_localizar_card_por_mes_no_formato_numerico():
    page = FakePage(visiveis={navegador.SELETOR_CARD}, textos_cards=["10/2026"])
    card = navegador.localizar_card(page, "10/2026")
    assert card.filtro_texto == "10/2026"


def test_localizar_card_por_mes_por_extenso():
    page = FakePage(visiveis={navegador.SELETOR_CARD}, textos_cards=["Outubro 2026"])
    card = navegador.localizar_card(page, "10/2026")
    assert card.filtro_texto == "Outubro 2026"


def test_localizar_card_mes_inexistente_levanta_fatura_nao_encontrada():
    page = FakePage(visiveis={navegador.SELETOR_CARD}, textos_cards=["Setembro 2026"])
    with pytest.raises(navegador.FaturaNaoEncontrada) as exc:
        navegador.localizar_card(page, "10/2026")
    assert "10/2026" in str(exc.value)


# --------------------------------------------------------------------------- #
# Download                                                                    #
# --------------------------------------------------------------------------- #
def test_baixar_pdf_do_card_salva_arquivo_no_diretorio(cfg):
    page = FakePage(visiveis={navegador.SELETOR_CARD})
    card = page.locator(navegador.SELETOR_CARD)

    destino = navegador.baixar_pdf_do_card(page, card, cfg.download_dir)

    assert destino == cfg.download_dir / "fatura.pdf"
    assert destino.read_bytes().startswith(b"%PDF")


def test_baixar_pdf_do_card_usa_fallback_quando_nome_vazio(cfg):
    page = FakePage(visiveis={navegador.SELETOR_CARD}, nome_download="")
    card = page.locator(navegador.SELETOR_CARD)

    destino = navegador.baixar_pdf_do_card(page, card, cfg.download_dir)

    assert destino.name == navegador.NOME_FALLBACK


def test_baixar_pdf_do_card_acrescenta_extensao_ausente(cfg):
    page = FakePage(visiveis={navegador.SELETOR_CARD}, nome_download="conta-outubro")
    card = page.locator(navegador.SELETOR_CARD)

    destino = navegador.baixar_pdf_do_card(page, card, cfg.download_dir)

    assert destino.name == "conta-outubro.pdf"


# --------------------------------------------------------------------------- #
# Fluxo completo                                                              #
# --------------------------------------------------------------------------- #
def test_navegar_e_baixar_executa_a_sequencia_completa(cfg):
    page = FakePage(
        visiveis={
            navegador.SELETOR_MENU_CONTAS,
            navegador.SELETOR_CARD,
            navegador.SELETOR_CARD_EM_ABERTO,
        }
    )

    destino = navegador.navegar_e_baixar(page, cfg)

    assert page.gotos[0][0] == cfg.faturas_url
    assert navegador.SELETOR_MENU_CONTAS in page.cliques
    assert destino.exists()


def test_navegar_e_baixar_com_mes_ref_nomeia_arquivo_por_mes(cfg):
    page = FakePage(
        visiveis={navegador.SELETOR_MENU_CONTAS, navegador.SELETOR_CARD},
        textos_cards=["10/2026"],
        nome_download="",  # força o nome de fallback
    )

    destino = navegador.navegar_e_baixar(page, cfg, "10/2026")

    assert destino.name == "fatura_10-2026.pdf"


def test_baixar_fatura_usa_sessao_e_contexto(cfg):
    sessao = FakeSession()
    destino = navegador.baixar_fatura(cfg=cfg, session=sessao, headless=True)

    assert sessao.ensure_chamado is True
    assert sessao.contexto_aberto is True
    assert sessao.headless_usado is True
    assert destino.exists()


def test_baixar_fatura_repassa_mes_ref_validado(cfg):
    sessao = FakeSession()
    with pytest.raises(ValueError):
        navegador.baixar_fatura("13/2026", cfg=cfg, session=sessao)
    # falha antes de abrir browser
    assert sessao.ensure_chamado is False
    assert sessao.contexto_aberto is False


def test_auth_mode_reuse_sem_sessao_falha_sem_abrir_browser(cfg):
    cfg_reuse = cfg.model_copy(update={"auth_mode": "reuse"})

    with pytest.raises(SessionExpired) as exc:
        navegador.baixar_fatura(cfg=cfg_reuse)

    assert "interactive" in str(exc.value)


def test_baixar_fatura_propaga_sessao_expirada(cfg):
    with pytest.raises(SessionExpired):
        navegador.baixar_fatura(cfg=cfg, session=FakeSession(valida=False))


