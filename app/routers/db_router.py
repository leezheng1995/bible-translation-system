from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import inspect, text

from app.core.database import DATABASE_URL, check_db_connection, engine


router = APIRouter(
    prefix="/db",
    tags=["db"],
)


def get_sqlite_path() -> str | None:
    if not DATABASE_URL.startswith("sqlite"):
        return None
    return DATABASE_URL.replace("sqlite:///", "", 1)


@router.get("/health")
def db_health():
    ok = check_db_connection()
    db_path = get_sqlite_path()

    return {
        "status": "ok" if ok else "error",
        "database_url": DATABASE_URL,
        "db_path": db_path,
        "db_exists": Path(db_path).exists() if db_path else None,
    }


@router.get("/tables")
def db_tables():
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())

    table_counts = {}

    with engine.connect() as conn:
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            table_counts[table] = result.scalar_one()

    return {
        "count": len(tables),
        "tables": tables,
        "table_counts": table_counts,
    }
