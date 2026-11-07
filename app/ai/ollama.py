"""Cliente OpenAI-compatible para o Ollama executado localmente."""

from __future__ import annotations

import json
from functools import lru_cache

from openai import OpenAI, OpenAIError
from sqlalchemy.orm import Session

from app.ai.config import ollama_settings
from app.ai.tools import FERRAMENTAS_OLLAMA, executar_ferramenta


class OllamaIndisponivel(RuntimeError):
    """O modelo local não respondeu à solicitação."""


@lru_cache(maxsize=1)
def _cliente() -> OpenAI:
    return OpenAI(
        base_url=ollama_settings.base_url,
        api_key=ollama_settings.api_key,
        timeout=ollama_settings.timeout_seconds,
    )


def gerar_resposta(system_prompt: str, user_prompt: str) -> str:
    try:
        resposta = _cliente().chat.completions.create(
            model=ollama_settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
    except OpenAIError as erro:
        raise OllamaIndisponivel(
            "Ollama não respondeu. Inicie o serviço local e confirme que o modelo "
            f"{ollama_settings.model!r} foi baixado."
        ) from erro

    conteudo = resposta.choices[0].message.content
    if not conteudo or not conteudo.strip():
        raise OllamaIndisponivel("Ollama retornou uma resposta vazia.")
    return conteudo.strip()


def responder_com_ferramentas(
    db: Session,
    system_prompt: str,
    pergunta: str,
    max_turnos: int = 4,
) -> str:
    """Executa somente as ferramentas de leitura permitidas e retorna a resposta."""
    mensagens = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": pergunta},
    ]
    try:
        for turno in range(max_turnos):
            resposta = _cliente().chat.completions.create(
                model=ollama_settings.model,
                messages=mensagens,
                tools=FERRAMENTAS_OLLAMA,
                tool_choice="required" if turno == 0 else "auto",
                temperature=0.1,
                max_tokens=256,
            )
            mensagem = resposta.choices[0].message
            chamadas = mensagem.tool_calls or []
            if not chamadas:
                conteudo = mensagem.content
                if conteudo and conteudo.strip():
                    return conteudo.strip()
                raise OllamaIndisponivel("Ollama retornou uma resposta vazia.")

            mensagens.append(mensagem.model_dump(exclude_none=True))
            for chamada in chamadas:
                try:
                    argumentos = json.loads(chamada.function.arguments or "{}")
                    resultado = executar_ferramenta(db, chamada.function.name, argumentos)
                except (json.JSONDecodeError, ValueError) as erro:
                    resultado = {"erro": str(erro)}
                mensagens.append(
                    {
                        "role": "tool",
                        "tool_call_id": chamada.id,
                        "content": json.dumps(
                            resultado, ensure_ascii=False, allow_nan=False
                        ),
                    }
                )
    except OpenAIError as erro:
        raise OllamaIndisponivel(
            "Ollama não respondeu. Inicie o serviço local e confirme que o modelo "
            f"{ollama_settings.model!r} foi baixado."
        ) from erro

    raise OllamaIndisponivel(
        "Ollama excedeu o limite de chamadas de ferramenta sem concluir a resposta."
    )