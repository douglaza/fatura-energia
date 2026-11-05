from pydantic import BaseModel, Field, field_validator


class PerguntaAI(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)

    @field_validator("pergunta")
    @classmethod
    def validar_pergunta(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("A pergunta não pode ficar vazia.")
        return valor


class RespostaAI(BaseModel):
    resposta: str


class ExplicacaoFatura(BaseModel):
    explicacao: str


class RecomendacaoEnergetica(BaseModel):
    recomendacao: str