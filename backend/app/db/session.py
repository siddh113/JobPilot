from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine, text

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jobpilot.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# create_all() only creates indexes for tables it creates from scratch —
# on an existing DB file (like anyone who was already running this before
# these indexes were added to the models) the table already exists, so
# create_all() is a no-op and the index never gets backfilled. These
# explicit statements make sure it happens either way; IF NOT EXISTS
# keeps re-running them on every startup free.
_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_posting_first_seen_at ON posting (first_seen_at)",
    "CREATE INDEX IF NOT EXISTS ix_posting_status ON posting (status)",
    "CREATE INDEX IF NOT EXISTS ix_posting_company_id ON posting (company_id)",
    "CREATE INDEX IF NOT EXISTS ix_matchscore_posting_id ON matchscore (posting_id)",
    "CREATE INDEX IF NOT EXISTS ix_application_posting_id ON application (posting_id)",
]


def init_db() -> None:
    # Import models so they're registered on SQLModel.metadata before create_all.
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
        for stmt in _INDEX_STATEMENTS:
            conn.execute(text(stmt))
        conn.commit()


def get_session() -> Session:
    return Session(engine)
