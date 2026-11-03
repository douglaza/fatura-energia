from app.crud.consumo import criar_consumo, listar_consumos
from app.crud.fatura import (
    atualizar_fatura,
    criar_fatura,
    deletar_fatura,
    listar_faturas,
    obter_fatura,
    obter_fatura_por_codigo,
)

__all__ = [
    "atualizar_fatura",
    "criar_consumo",
    "criar_fatura",
    "deletar_fatura",
    "listar_consumos",
    "listar_faturas",
    "obter_fatura",
    "obter_fatura_por_codigo",
]

