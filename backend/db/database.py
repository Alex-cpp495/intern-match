import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_SQLITE = f"sqlite:///{_BACKEND_DIR / 'data' / 'app.db'}"
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from db import models  # noqa: F401 — register models

    Base.metadata.create_all(bind=engine)
