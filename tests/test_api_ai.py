from datetime import date, datetime
from decimal import Decimal

import pytest

from app.ai import assistant
from app.ai.ollama import OllamaIndisponivel
from app.models.consumo import Consumo
from app.models.fatura import Fatura


def criar_fatura(db, mes, kwh, valor):
    fatura = Fatura(
        codigo_fatura=f"AI-{mes}",
        instalacao="1234567890",
        titular="CLIENTE DE TESTE",
        mes_referencia=mes,
        data_emissao=datetime.fromisoformat(f"{mes}-10"),
        vencimento=datetime.fromisoformat(f"{mes}-25"),
        valor_total=Decimal(str(valor)),
        consumo_kwh=Decimal(str(kwh)),
        consumos=[Consumo(data_leitura=date.fromisoformat(f"{mes}-15"), kwh=kwh)],
    )
    db.add(fatura)
    db.commit()
    return fatura


def test_explicar_fatura_usa_contexto_agregado(client, db, monkeypatch):
    criar_fatura(db, "2026-09", 100, 120)
    criar_fatura(db, "2026-10", 120, 150)
    prompt_recebido = {}

    def fake_llm(system_prompt, user_prompt):
        prompt_recebido["system"] = system_prompt
        prompt_recebido["user"] = user_prompt
        return "Houve aumento de 20,0% para 120 kWh. A fatura foi R$ 150,00."

    monkeypatch.setattr(assistant, "gerar_resposta", fake_llm)

    response = client.get("/ai/faturas/2026-10/explicar")

    assert response.status_code == 200
    assert "aumento de 20,0%" in response.json()["explicacao"]
    assert "R$ 150,00" in response.json()["explicacao"]
    assert "CLIENTE DE TESTE" not in prompt_recebido["user"]
    assert "1234567890" not in prompt_recebido["user"]
    assert '"consumo_kwh": 120.0' in prompt_recebido["user"]


def test_explicar_fatura_inexistente_retorna_404(client):
    assert client.get("/ai/faturas/2026-10/explicar").status_code == 404


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        ("Qual foi meu maior consumo?", "Março/2026\n389,00 kWh"),
        ("Qual foi minha conta mais cara?", "Fevereiro/2026\nR$ 200,00"),
        (
            "Quais foram os três meses mais recentes de consumo e seus valores em kWh?",
            "Agosto/2026: 186,00 kWh\nSetembro/2026: 235,00 kWh\nOutubro/2026: 268,00 kWh",
        ),
        ("Quantas faturas existem no banco?", "Há 3 fatura(s) cadastrada(s) neste banco."),
        (
            "Quantas faturas existem no banco e qual o valor total delas?",
            "Há 3 fatura(s) cadastrada(s), com valor total de R$ 450,00.",
        ),
        (
            "Qual é o valor total das faturas?",
            "O valor total das 3 fatura(s) cadastradas é R$ 450,00.",
        ),
        ("Quanto consumi em 2026?", "O consumo registrado em 2026 foi de 639,00 kWh."),
        ("Quanto gasto em média?", "O gasto médio por fatura cadastrada é R$ 150,00."),
    ],
)
def test_chat_responde_perguntas_com_dados_do_banco(client, db, pergunta, esperado):
    criar_fatura(db, "2026-01", 100, 100)
    criar_fatura(db, "2026-02", 150, 200)
    criar_fatura(db, "2026-03", 389, 150)

    response = client.post("/ai/chat", json={"pergunta": pergunta})

    assert response.status_code == 200
    assert response.json()["resposta"] == esperado


def test_consultor_energetico_sem_historico_responde_com_limite_claro(client):
    response = client.post("/ai/consultor")

    assert response.status_code == 200
    assert "não há histórico" in response.json()["recomendacao"].lower()


def test_chat_aberto_usa_llm_com_contexto_agregado(client, db, monkeypatch):
    criar_fatura(db, "2026-10", 120, 150)
    chamada_recebida = {}

    def fake_tools(db_recebido, system_prompt, pergunta):
        chamada_recebida["db"] = db_recebido
        chamada_recebida["pergunta"] = pergunta
        return "O histórico disponível registra 120 kWh em outubro."

    monkeypatch.setattr(assistant, "responder_com_ferramentas", fake_tools)
    response = client.post(
        "/ai/chat",
        json={"pergunta": "Como meu consumo mudou recentemente?"},
    )

    assert response.status_code == 200
    assert "120 kWh" in response.json()["resposta"]
    assert chamada_recebida["db"] is db
    assert chamada_recebida["pergunta"] == "Como meu consumo mudou recentemente?"


def test_ollama_indisponivel_retorna_503(client, db, monkeypatch):
    criar_fatura(db, "2026-10", 120, 150)

    def indisponivel(*_args):
        raise OllamaIndisponivel("Ollama indisponível para o teste.")

    monkeypatch.setattr(assistant, "gerar_resposta", indisponivel)
    response = client.get("/ai/faturas/2026-10/explicar")

    assert response.status_code == 503
    assert "Ollama indisponível" in response.json()["detail"]


def test_chat_rejeita_pergunta_vazia(client):
    response = client.post("/ai/chat", json={"pergunta": "   "})

    assert response.status_code == 422