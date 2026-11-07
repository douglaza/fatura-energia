from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.ai.ollama import responder_com_ferramentas
from app.ai.tools import executar_ferramenta
from app.models.consumo import Consumo
from app.models.fatura import Fatura


def criar_fatura(db, mes, consumo, valor):
    fatura = Fatura(
        codigo_fatura=f"TOOL-{mes}",
        instalacao="1234567890",
        titular="DADO PRIVADO",
        mes_referencia=mes,
        data_emissao=datetime.fromisoformat(f"{mes}-10"),
        vencimento=datetime.fromisoformat(f"{mes}-25"),
        valor_total=Decimal(str(valor)),
        consumo_kwh=Decimal(str(consumo)),
        consumos=[Consumo(data_leitura=date.fromisoformat(f"{mes}-15"), kwh=consumo)],
    )
    db.add(fatura)
    db.commit()
    return fatura


def test_ferramentas_consultam_resumo_do_banco_sem_dados_pessoais(db):
    criar_fatura(db, "2026-01", 100, 120)
    criar_fatura(db, "2026-02", 200, 180)

    consumo = executar_ferramenta(db, "resumir_consumo", {"ano": 2026})
    faturas = executar_ferramenta(db, "resumir_faturas", {"ano": 2026})
    historico = executar_ferramenta(
        db, "listar_historico_consumo", {"ano": 2026, "limite": 1}
    )

    assert consumo["consumo_total_kwh"] == 300
    assert consumo["consumo_mensal"] == [
        {"mes": "2026-01", "kwh": 100.0},
        {"mes": "2026-02", "kwh": 200.0},
    ]
    assert consumo["maior_consumo"] == {"mes": "2026-02", "kwh": 200.0}
    assert faturas["quantidade"] == 2
    assert faturas["valor_total_brl"] == 300
    assert historico["meses"] == [{"mes": "2026-02", "consumo_kwh": 200.0}]
    assert "DADO PRIVADO" not in str((consumo, faturas, historico))
    assert "1234567890" not in str((consumo, faturas, historico))


def test_tool_call_consulta_banco_e_devolve_resultado_ao_modelo(db, monkeypatch):
    criar_fatura(db, "2026-01", 100, 120)
    capturadas = []

    chamada = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="resumir_consumo",
            arguments='{"ano":2026}',
        ),
    )
    mensagem_tool = SimpleNamespace(
        content=None,
        tool_calls=[chamada],
        model_dump=lambda exclude_none=True: {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "resumir_consumo",
                        "arguments": '{"ano":2026}',
                    },
                }
            ],
        },
    )
    mensagem_final = SimpleNamespace(content="O total foi 100 kWh.", tool_calls=None)

    class FakeCompletions:
        def create(self, **kwargs):
            capturadas.append(kwargs)
            mensagem = mensagem_tool if len(capturadas) == 1 else mensagem_final
            return SimpleNamespace(choices=[SimpleNamespace(message=mensagem)])

    cliente = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )
    monkeypatch.setattr("app.ai.ollama._cliente", lambda: cliente)

    resposta = responder_com_ferramentas(db, "Use ferramentas", "Quanto consumi em 2026?")

    assert resposta == "O total foi 100 kWh."
    assert capturadas[0]["tools"]
    retorno_tool = capturadas[1]["messages"][-1]
    assert retorno_tool["role"] == "tool"
    assert '"consumo_total_kwh": 100.0' in retorno_tool["content"]
    assert "DADO PRIVADO" not in retorno_tool["content"]


def test_tool_call_rejeita_funcao_nao_allowlisted(db):
    try:
        executar_ferramenta(db, "executar_sql", {"sql": "DELETE FROM faturas"})
    except ValueError as erro:
        assert "não permitida" in str(erro)
    else:
        raise AssertionError("Ferramentas fora da allowlist devem ser rejeitadas.")