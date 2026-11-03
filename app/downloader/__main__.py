"""Linha de comando da automação de download.

⚠️ v1: o login é **manual a cada execução** — o browser abre, você faz o
login e resolve o reCAPTCHA, e o robô continua sozinho a partir daí.

Exemplos::

    python -m app.downloader                     # fatura em aberto
    python -m app.downloader --mes 10/2026       # mês específico
    python -m app.downloader -v                  # com log detalhado
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.downloader.auth import SessionExpired
from app.downloader.navegador import FaturaNaoEncontrada, baixar_fatura


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.downloader",
        description=(
            "Baixa faturas de energia do portal CEMIG. "
            "O login é manual: o browser abre e você resolve o reCAPTCHA."
        ),
    )
    parser.add_argument(
        "--mes",
        metavar="MM/AAAA",
        help="mês de referência da fatura (padrão: a fatura em aberto)",
    )
    # --- [PERSISTÊNCIA] opções que só fazem sentido com sessão salva --------
    # parser.add_argument(
    #     "--headless",
    #     action="store_true",
    #     help="roda o Chromium sem janela (exige sessão já salva)",
    # )
    # parser.add_argument(
    #     "--login",
    #     action="store_true",
    #     help="apenas faz o login interativo e salva a sessão, sem baixar nada",
    # )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="mostra log detalhado (DEBUG)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        # --- [PERSISTÊNCIA] login isolado (--login), sem baixar -------------
        # if args.login:
        #     SessionManager(settings).login_interactive(headless=False)
        #     print(f"\nSessão salva em: {settings.state_file}")
        #     return 0
        #
        # caminho = baixar_fatura(args.mes, headless=args.headless or None)

        caminho = baixar_fatura(args.mes)
    except (SessionExpired, FaturaNaoEncontrada, ValueError) as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1

    print(f"Fatura salva em: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
