import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base

TEST_DB_URL = "sqlite:///./test.db"

FIXTURES = Path(__file__).parent / "fixtures"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def criar_banco():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def banco_limpo():
    with TestingSessionLocal() as session:
        for tabela in reversed(Base.metadata.sorted_tables):
            session.execute(tabela.delete())
        session.commit()
    yield


@pytest.fixture
def db() -> Session:
    session = TestingSessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(db: Session) -> Session:
    return db


# @pytest.fixture
# def fixture_pdf(tmp_path: Path) -> dict:
#     src = Path(__file__).parent / "fixtures" / "fatura_exemplo.pdf"
#     dest = tmp_path / "fatura_exemplo.pdf"
#     shutil.copy(src, dest)
#     return {"pdf": ("fatura_exemplo.pdf", dest.read_bytes(), "application/pdf")}

@pytest.fixture
def fixture_pdf():
    return {
        "pdf": (
            "fatura.pdf",
            (FIXTURES / "fatura.pdf").read_bytes(),
            "application/pdf",
        )
    }