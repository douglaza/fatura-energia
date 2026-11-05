# cemig-bill

Pipeline automatizado para **download, parsing e armazenamento de faturas CEMIG**, com API FastAPI e banco PostgreSQL.

## Funcionalidades

- 🤖 **Downloader** — navegação automatizada com Playwright (login com reCAPTCHA resolvido pelo humano, dispensa de banner de cookies, acesso à página de detalhes da fatura e download do PDF). A sessão vive em memória durante a execução; o login é solicitado a cada execução nesta fase (v1).
- 📄 **Parser** — extração de titular, vencimento, consumo kWh, referência e histórico mensal dos PDFs CEMIG com pdfplumber/pdfminer.
- 🗄️ **PostgreSQL** — modelos SQLAlchemy + migrações Alembic (`faturas`, `consumos`).
- 🔌 **API REST** — endpoints para consulta de faturas/consumos e upload manual de PDFs.
- 📊 **Dashboard Excel** — exportação de indicadores, histórico, faturas e gráficos via OpenPyXL.
- 🔄 **Pipeline** — orquestra parser → persistência (`app/pipeline.py`), disparável via `python -m app.downloader --persistir`.
- ✅ **Testes** — 73 testes pytest cobrindo parser, CRUD, API, relacionamentos, downloader (dublês sem browser), pipeline e dashboard.

## Stack

Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL · Playwright · pdfplumber · pandas · OpenPyXL · pytest

## Estrutura

    cemig-bill/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py              # app FastAPI e roteadores (faturas, upload)
    │   ├── pipeline.py          # orquestra parser → persistência
    │   ├── analytics/           # indicadores, relatórios pandas e dashboard OpenPyXL
    │   ├── core/                # config.py (Settings) + database.py (conexão)
    │   ├── crud/                # operações de banco (fatura, consumo)
    │   ├── db/                  # models SQLAlchemy (fatura, consumo) + repo
    │   ├── models/              # modelos ORM (fatura, consumo)
    │   ├── schemas/             # schemas Pydantic (entrada/saída)
    │   ├── routers/             # endpoints FastAPI (faturas, consumos, upload, relatórios)
    │   ├── downloader/          # automação de login e download (Playwright)
    │   │   ├── auth.py          # SessionManager (login, reCAPTCHA, sessão em memória)
    │   │   ├── config.py        # CemigSettings (variáveis CEMIG_*)
    │   │   ├── navegador.py     # navegação até as faturas e download do PDF
    │   │   └── __main__.py      # CLI: python -m app.downloader
    │   └── parser/              # extração de dados dos PDFs (cemig.py, pdf.py)
    ├── migrations/              # migrações Alembic
    ├── scripts/                 # utilitários (gerar_fixture_pdf.py)
    ├── tests/                   # suíte de testes pytest
    ├── docker-compose.yml       # banco PostgreSQL (dev, porta 5432)
    ├── docker-compose.test.yml  # banco PostgreSQL (testes, porta 5433)
    ├── .env.example             # variáveis de ambiente (copie para .env)
    ├── requirements.txt
    └── README.md

## Setup

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Variáveis de ambiente
cp .env.example .env
# edite .env com DATABASE_URL e, opcionalmente, CEMIG_USER / CEMIG_PASSWORD

# 3. Banco de dados
docker compose up -d
alembic upgrade head
```

## Uso

**Baixar faturas** (navegação automatizada; login manual com reCAPTCHA):

```bash
python -m app.downloader             # fatura em aberto
python -m app.downloader --mes 10/2026   # mês específico
python -m app.downloader --persistir     # baixa e grava no PostgreSQL
python -m app.downloader -v              # log detalhado
```

Saída: PDF em `data/raw/` (configurável via `CEMIG_DOWNLOAD_DIR`).

**Subir a API**:

```bash
uvicorn app.main:app --reload
```

Docs interativas em `http://localhost:8000/docs`.

**Upload manual de fatura**:

```bash
curl -X POST http://localhost:8000/faturas/upload \
  -F "pdf=@data/raw/fatura.pdf"
```

**Baixar dashboard Excel** (com a API em execução e o banco configurado):

```bash
curl -o dashboard_consumo.xlsx http://localhost:8000/relatorios/dashboard.xlsx
```

O arquivo contém quatro abas: **Resumo Executivo** (consumo médio, projeção,
maior e menor consumo, valores e tendência), **Histórico**, **Faturas** e
**Gráficos**. As leituras do histórico são organizadas por mês; o dashboard não
soma todos os meses de uma fatura como se fossem um único consumo. Se várias
faturas contiverem a mesma leitura mensal, ela aparece uma só vez. Os valores
financeiros consideram as faturas cadastradas; meses sem fatura ficam sem valor
na série de gastos.

A projeção do próximo mês é a média dos consumos válidos de até três meses mais
recentes. É uma média móvel simples e não considera sazonalidade. Veja também
[cemigbill1.html](cemigbill1.html).

**Testes**:

```bash
pytest -v
```

## Configuração (`.env`)

| Variável              | Descrição                                               |
| ---------------------- | --------------------------------------------------------- |
| `DATABASE_URL`       | URL de conexão PostgreSQL                                |
| `POSTGRES_*`         | Credenciais do container Postgres                         |
| `CEMIG_USER`         | Usuário do portal CEMIG (e-mail ou CPF)                  |
| `CEMIG_PASSWORD`     | Senha do portal CEMIG                                     |
| `CEMIG_INSTALACAO`   | Número da instalação (opcional)                        |
| `CEMIG_DOWNLOAD_DIR` | Pasta onde o PDF baixado é salvo (padrão: `data/raw`) |
| `CEMIG_HEADLESS`     | Rodar Chromium sem janela (padrão: `false`)            |

## Roadmap

- [X] Download automatizado de faturas (login manual com reCAPTCHA)
- [X] Parser de PDF
- [X] Integração download → parser → PostgreSQL (`--persistir` + `app/pipeline.py`)
- [ ] Armazenar o PDF original em disco e salvar o caminho na fatura (nova coluna `arquivo_pdf`, nova migration Alembic)
- [ ] Encadear download → upload sem intervenção humana
- [X] Histórico consolidado e dashboard Excel com indicadores e gráficos
- [ ] Manter seletores do portal em constantes para ajuste rápido quando mudarem

## Segurança

- `.env`, `data/`, `pdfs_armazenados/` e `**/storage_state.json` **nunca** são versionados (ver `.gitignore`).
- O login usa reCAPTCHA v2: o humano resolve o desafio uma vez por execução; a automação total do login violaria os ToS do Google e da CEMIG.

## Status

> Projeto em desenvolvimento ativo. Download, parsing, API, integração download → parser → banco e exportação do dashboard Excel funcionando. Login continua manual (reCAPTCHA) a cada execução nesta fase (v1).
