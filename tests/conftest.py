import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base   # <-- caminho real do seu projeto

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Cria todas as tabelas uma vez por sessão de testes."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    """Sessão de banco isolada por teste (rollback ao final)."""
    session = TestingSession()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def client(db: Session):
    """TestClient com get_db sobrescrito para usar a sessão de teste."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(db: Session) -> Session:
    """Alias — alguns testes usam db_session, outros db."""
    return db


@pytest.fixture
def fixture_pdf(tmp_path: Path) -> Path:
    """Copia um PDF de exemplo para um diretório temporário."""
    import shutil

    src = Path(__file__).parent / "fixtures" / "fatura_exemplo.pdf"
    dest = tmp_path / "fatura_exemplo.pdf"
    shutil.copy(src, dest)
    return dest
