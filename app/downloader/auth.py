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
from typing import TYPE_CHECKING

from app.core.config import Settings, settings

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
    "[aria-label*='Aceitar']",
    "button#accept-all-button",
)


class SessionExpired(RuntimeError):
    """Sessão inválida e não foi possível renová-la automaticamente."""


# --------------------------------------------------------------------------- #
# JWT — desativado com a persistência da sessão                                #
# --------------------------------------------------------------------------- #
# Só faz sentido ler a expiração do token quando existe um estado salvo para
# inspecionar. Reative estes helpers junto com o bloco de persistência.
#
# def decodificar_jwt(token: str) -> dict:
#     """Decodifica o payload de um JWT **sem** verificar a assinatura.
#
#     Serve só para ler claims (``exp``, ``sub``). Nunca use o conteúdo como
#     prova de autenticidade.
#     """
#     try:
#         payload_b64 = token.split(".")[1]
#     except IndexError as e:
#         raise SessionExpired(f"Token malformado: {e}") from e
#
#     padding = "=" * (-len(payload_b64) % 4)  # JWT usa base64url sem padding
#     try:
#         return json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
#     except (ValueError, json.JSONDecodeError) as e:
#         raise SessionExpired(f"Token malformado: {e}") from e
#
#
# def expiracao_do_token(token: str) -> datetime | None:
#     """Data/hora (UTC) de expiração do token, ou ``None`` se não houver ``exp``."""
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

    def __init__(self, cfg: Settings = settings):
        self.cfg = cfg
        #: ``storage_state`` capturado no login e reutilizado no contexto de
        #: navegação — nunca gravado em disco nesta versão.
        self._state: dict | None = None

    @property
    def autenticado(self) -> bool:
        """``True`` se já houve login nesta execução (sessão em memória)."""
        return self._state is not None

    # --------------------- estado salvo em disco (a reativar) ------------- #
    # def _load_state(self) -> dict:
    #     if not self.cfg.state_file.exists():
    #         raise SessionExpired(
    #             f"{self.cfg.state_file} não encontrado. "
    #             "Rode o login interativo (python -m app.downloader --login)."
    #         )
    #     try:
    #         return json.loads(self.cfg.state_file.read_text(encoding="utf-8"))
    #     except (OSError, json.JSONDecodeError) as e:
    #         raise SessionExpired(f"Estado de sessão ilegível: {e}") from e
    #
    # @staticmethod
    # def _cookie(state: dict, nome: str) -> str | None:
    #     for cookie in state.get("cookies", []):
    #         if cookie.get("name") == nome:
    #             return cookie.get("value")
    #     return None
    #
    # def is_session_valid(self, margin_minutes: int | None = None) -> bool:
    #     """``True`` se o access-token existe e expira depois da margem de segurança."""
    #     margem = margin_minutes or self.cfg.token_refresh_margin_minutes
    #     try:
    #         state = self._load_state()
    #     except SessionExpired:
    #         return False
    #
    #     token = self._cookie(state, TOKEN_COOKIE)
    #     if not token:
    #         return False
    #
    #     expira_em = expiracao_do_token(token)
    #     if expira_em is None:
    #         return False
    #
    #     limite = datetime.now(timezone.utc) + timedelta(minutes=margem)
    #     valida = expira_em > limite
    #     logger.debug("Token expira em %s (válida: %s)", expira_em.isoformat(), valida)
    #     return valida
    #
    # def token_expiry(self) -> datetime | None:
    #     """Expiração do token atual — útil para logs/monitoramento."""
    #     try:
    #         token = self._cookie(self._load_state(), TOKEN_COOKIE)
    #     except SessionExpired:
    #         return None
    #     return expiracao_do_token(token) if token else None

    # ----------------------------- garantia ------------------------------- #
    def ensure_valid(self) -> None:
        """Garante uma sessão para a execução; se não houver, pede o login.

        Sem persistência não existe "sessão anterior": a cada processo o
        browser abre e o login (com captcha) é feito manualmente.
        """
        if self.autenticado:
            logger.info("Sessão em memória já disponível para esta execução.")
            return

        logger.info("Nenhuma sessão — abrindo o browser para login manual.")
        self.login_interactive(headless=False)  # captcha exige tela
        if not self.autenticado:
            raise SessionExpired("Login não produziu uma sessão válida.")

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
                self._try_autofill(page)

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
                # context.storage_state(path=str(self.cfg.state_file))
                # logger.info("Sessão salva em %s", self.cfg.state_file)

                logger.info("Sessão capturada em memória (persistência desativada).")
            finally:
                browser.close()

    def _try_autofill(self, page: Page) -> None:
        """Pré-preenche usuário/senha quando as credenciais estão no .env.

        O captcha continua manual — qualquer falha aqui é silenciosa e o
        login segue 100% manual.
        """
        if not (self.cfg.user and self.cfg.password):
            logger.info("Credenciais não configuradas — login totalmente manual.")
            return
        try:
            campo_usuario = page.locator('input[name="cpf"], input[type="text"]').first
            campo_usuario.wait_for(timeout=5_000)
            campo_usuario.fill(self.cfg.user)
            page.locator('input[type="password"]').first.fill(self.cfg.password)
            page.locator('button[type="submit"], button:has-text("Entrar")').first.click()
            logger.info("Credenciais pré-preenchidas; falta o captcha.")
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
                storage_state=self._state,
                user_agent=self.cfg.user_agent,
                locale="pt-BR",
                accept_downloads=True,
            )
            yield context.new_page()
        finally:
            browser.close()
            pw.stop()
