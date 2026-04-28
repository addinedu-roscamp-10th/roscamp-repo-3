from functools import lru_cache
from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parent / "sql"


@lru_cache
def load_sql(relative_path: str) -> str:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"SQL path must stay under {SQL_ROOT}: {relative_path}")

    sql_path = SQL_ROOT / path
    if sql_path.suffix != ".sql":
        raise ValueError(f"SQL file must use .sql extension: {relative_path}")

    return sql_path.read_text(encoding="utf-8").strip()


__all__ = ["SQL_ROOT", "load_sql"]
