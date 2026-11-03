"""Autenticação no portal CEMIG — **login manual a cada execução**.

⚠️ ESTADO ATUAL (v1): a persistência da sessão está **desativada**.

1. O portal protege o login com **reCAPTCHA v2**, o que torna o login 100%
   automatizado inviável de forma legítima. Aceitamos o limite: o humano
   resolve o desafio no browser aberto pelo Playwright.
2. A sessão vive **apenas em memória** (``self._state``) durante a execução:
   o ``storage_state`` é copiado do contexto de login para o contexto de
   navegação e descartado no final. **Nada é gravado em disco.**
3. Consequência: **toda execução pede login + captcha**. Isso é intencional
   nesta fase do projeto.
4. A persistência em ``storage_state.json`` volta quando o restante do
   projeto estiver pronto: todo o código original está preservado nos blocos
   marcados com ``# --- [PERSISTÊNCIA] ---``, bastando descomentar.

``playwright`` é importado **dentro** das funções: assim o pacote pode ser
importado (e testado) em máquinas sem o browser instalado.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from app.downloader.config import CemigSettings, cemig_settings

# --- [PERSISTÊNCIA] imports usados apenas pela sessão persistida ------------
# import base64
# import json
# from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:  # apenas para tipagem — nada é importado em runtime
    from collections.abc import Iterator

    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

# --- [PERSISTÊNCIA] cookie onde o next-auth guarda o JWT de acesso ----------
# TOKEN_COOKIE = "__Secure-next-auth.access-token"

#: Trecho comum aos cookies de sessão (next-auth.session-token, etc.).
SESSION_COOKIE_HINT = "next-auth"

#: Tempo máximo para o humano concluir login + captcha (5 min).
LOGIN_TIMEOUT_MS = 300_000

#: Seletores de banners de consentimento (LGPD/OneTrust/etc.).
COOKIE_SELECTORS = (
    "#onetrust-accept-btn-handler",
    "button:has-text('Aceitar todos')",
    "button:has-text('Aceitar Todos')",
    "button:has-text('Aceitar cookies')",
    "button:has-text('Concordo')",
    "button[aria-label*='Aceitar']",   # restringido a <button> clicável
    "button#accept-all-button",
)


class SessionExpired(RuntimeError):
    """Sessão inválida e não foi possível renová-la automaticamente."""


# --------------------------------------------------------------------------- #
# JWT — desativado com a persistência da sessão                                #
# --------------------------------------------------------------------------- #
# def decodificar_jwt(token: str) -> dict:
#     try:
#         payload_b64 = token.split(".")[1]
#     except IndexError as e:
#         raise SessionExpired(f"Token malformado: {e}") from e
#     padding = "=" * (-len(payload_b64) % 4)
#     try:
#         return json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
#     except (ValueError, json.JSONDecodeError) as e:
#         raise SessionExpired(f"Token malformado: {e}") from e
#
# def expiracao_do_token(token: str) -> datetime | None:
#     try:
#         exp = decodificar_jwt(token).get("exp")
#     except SessionExpired:
#         return None
#     if exp is None:
#         return None
#     return datetime.fromtimestamp(exp, tz=timezone.utc)


# --------------------------------------------------------------------------- #
# Banner de cookies                                                            #
# --------------------------------------------------------------------------- #
def dispensar_cookies(page: Page) -> None:
    """Fecha o banner de cookies, se presente. Idempotente e tolerante a falha."""
    for seletor in COOKIE_SELECTORS:
        try:
            botao = page.locator(seletor).first
            if botao.is_visible(timeout=1_500):
                botao.click()
                logger.info("Banner de cookies dispensado via %s", seletor)
                page.wait_for_timeout(1_000)
                return
        except Exception:  # o seletor pode não existir — segue tentando
            continue
    logger.debug("Nenhum banner de cookies encontrado.")


# --------------------------------------------------------------------------- #
# Gerenciador de sessão                                                        #
# --------------------------------------------------------------------------- #
class SessionManager:
    """Cuida da sessão autenticada no portal CEMIG.

    v1: a sessão é mantida **apenas em memória** (``self._state``) e o login
    é refeito manualmente em cada execução. A persistência em
    ``storage_state.json`` está comentada — procure por ``[PERSISTÊNCIA]``.
    """

    def __init__(self, cfg: CemigSettings = cemig_settings):
        self.cfg = cfg
        #: ``storage_state`` capturado no login e reutilizado no contexto de
        #: navegação — nunca gravado em disco nesta versão.
        self._state: Optional[dict[str, Any]] = None

    @property
    def autenticado(self) -> bool:
        """``True`` se já houve login nesta execução (sessão em memória)."""
        return self._state is not None

    # ----------------------------- garantia ------------------------------- #
    def ensure_valid(self) -> bool:
        """Garante uma sessão para a execução; se não houver, pede o login.

        Retorna ``True`` se a sessão ficou disponível.
        """
        if self.autenticado:
            logger.info("Sessão em memória já disponível para esta execução.")
            return True

        logger.info("Nenhuma sessão — abrindo o browser para login manual.")
        self.login_interactive(headless=False)  # captcha exige tela
        if not self.autenticado:
            raise SessionExpired("Login não produziu uma sessão válida.")
        return True

    # ------------------------------- login -------------------------------- #
    def login_interactive(self, headless: bool = False) -> None:
        """Abre o browser para login manual e guarda a sessão **em memória**.

        Nada é gravado em disco: o ``storage_state`` fica em ``self._state`` e
        morre junto com o processo (ver ``# --- [PERSISTÊNCIA] ---``).
        """
        from playwright.sync_api import sync_playwright

        # --- [PERSISTÊNCIA] garante a pasta do arquivo de estado ------------
        # self.cfg.state_file.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            try:
                context = browser.new_context(
                    user_agent=self.cfg.user_agent,
                    locale="pt-BR",
                )
                page = context.new_page()

                logger.info("Abrindo página de login: %s", self.cfg.login_url)
                page.goto(self.cfg.login_url, wait_until="domcontentloaded")
                dispensar_cookies(page)
                self._preencher_credenciais(page)

                print("\n>>> Conclua o login (e o reCAPTCHA) no browser aberto.")
                print(">>> Aguardando o redirecionamento para /portal/home ...")

                page.wait_for_url(re.compile(r"/portal/home"), timeout=LOGIN_TIMEOUT_MS)
                dispensar_cookies(page)

                cookies = context.cookies()
                if not any(SESSION_COOKIE_HINT in c["name"] for c in cookies):
                    raise SessionExpired(
                        "Login concluído, mas cookies de sessão (next-auth) ausentes."
                    )

                # Sessão viva apenas em memória — reutilizada em abrir_contexto().
                self._state = context.storage_state()

                # --- [PERSISTÊNCIA] gravação do estado em disco (a reativar) --
                context.storage_state(path=str(self.cfg.state_file))
                logger.info("Sessão salva em %s", self.cfg.state_file)

                logger.info("Sessão capturada em memória (persistência desativada).")
            finally:
                browser.close()

    def _preencher_credenciais(self, page: Page) -> None:
        """Pré-preenche usuário/senha quando as credenciais estão no .env.

        ⚠️ NÃO clica em submit: o captcha ainda não foi resolvido, e o clique
        dispararia erro de validação no portal. O humano resolve o captcha
        e envia o formulário manualmente. Qualquer falha aqui é silenciosa.
        """
        if not (self.cfg.user and self.cfg.password):
            logger.info("Credenciais não configuradas — login totalmente manual.")
            return
        try:
            campo_usuario = page.locator('input[name="cpf"], input[type="text"]').first
            campo_usuario.wait_for(timeout=5_000)
            campo_usuario.fill(self.cfg.user)
            page.locator('input[type="password"]').first.fill(self.cfg.password)
            logger.info("Credenciais pré-preenchidas; humano resolve captcha e envia.")
        except Exception:
            logger.warning("Autofill falhou — login manual a partir daqui.")

    # --------------------------- browser pronto --------------------------- #
    @contextmanager
    def abrir_contexto(self, headless: bool = True) -> Iterator[Page]:
        """Abre o Chromium com a sessão em memória e garante o fechamento.

        A sessão vem de ``self._state`` (capturada por ``ensure_valid``), não
        de arquivo. Sem sessão, o contexto abre sem autenticação e a navegação
        falha cedo em ``navegar_ate_faturas``.
        """
        from playwright.sync_api import sync_playwright

        # --- [PERSISTÊNCIA] exigir o arquivo de estado (a reativar) ----------
        # if not self.cfg.state_file.exists():
        #     raise SessionExpired(
        #         f"{self.cfg.state_file} não encontrado. "
        #         "Rode o login interativo (python -m app.downloader --login)."
        #     )

        if self._state is None:
            logger.warning(
                "Abrindo contexto sem sessão autenticada — "
                "a navegação deve falhar no redirect para o login."
            )

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                # --- [PERSISTÊNCIA] estado lido do arquivo (a reativar) ------
                # storage_state=str(self.cfg.state_file),
                storage_state=self._state if self._state else None,  # None → contexto limpo
                user_agent=self.cfg.user_agent,
                locale="pt-BR",
                accept_downloads=True,
            )
            yield context.new_page()
        finally:
            browser.close()
            pw.stop()

