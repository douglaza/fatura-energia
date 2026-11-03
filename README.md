# cemig-bill

Pipeline automatizado para **download, parsing e armazenamento de faturas CEMIG**, com API FastAPI e banco PostgreSQL.

## Funcionalidades

- 🤖 **Downloader** — navegação automatizada com Playwright (login, dispensa de banner de cookies, acesso à página de detalhes da fatura e download do PDF), com sessão persistida via `storage_state.json`
- 📄 **Parser** — extração de dados (vencimento, consumo kWh, valor, referência) dos PDFs
- 🗄️ **PostgreSQL** — modelos SQLAlchemy + migrações Alembic (`faturas`, `consumos`)
- 🔌 **API REST** — endpoints para consulta de faturas/consumos e upload manual de PDFs
- ✅ **Testes** — suíte pytest cobrindo parser, CRUD, API e relacionamentos

## Stack

Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL · Playwright · pdfplumber · pytest

## Estrutura

    app/
    ├── downloader/   # automação de login e download (Playwright)
    ├── parser/       # extração de dados dos PDFs
    ├── models/       # modelos ORM
    ├── schemas/      # schemas Pydantic
    ├── crud/         # operações de banco
    ├── routers/      # endpoints FastAPI
    └── core/         # configuração e conexão de banco
    migrations/       # migrações Alembic
    tests/            # suíte de testes
    scripts/          # utilitários

## Setup

    # 1. Ambiente virtual
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium

    # 2. Variáveis de ambiente
    cp .env.example .env
    # edite .env com suas credenciais CEMIG e do banco

    # 3. Banco de dados
    docker compose up -d
    alembic upgrade head

## Uso

**Baixar faturas** (navegação automatizada):

    python -m app.downloader -v

**Subir a API**:

    uvicorn app.main:app --reload

Docs interativas em `http://localhost:8000/docs`.

**Upload manual de fatura**:

    curl -X POST http://localhost:8000/api/upload \
      -F "arquivo=@fatura.pdf"

**Testes**:

    pytest -v

## Configuração (`.env`)

| Variável           | Descrição                          |
|--------------------|------------------------------------|
| `CEMIG_USER`       | Usuário do portal CEMIG            |
| `CEMIG_PASSWORD`   | Senha do portal CEMIG              |
| `DATABASE_URL`     | URL de conexão PostgreSQL          |
| `POSTGRES_*`       | Credenciais do container Postgres  |

## Roadmap

- [x] Download automatizado de faturas
- [x] Parser de PDF
- [ ] **Integração: download → parser → PostgreSQL**
- [ ] Histórico de consumo consolidado / dashboards

## Segurança

- `.env`, `data/` e `storage_state.json` **nunca** são versionados (ver `.gitignore`)
- `storage_state.json` contém cookies de sessão — trate como credencial

## Status

> Projeto em desenvolvimento ativo. Pipeline de download e parsing funcionando;
> integração download → parser → banco em andamento.

