"""Small helpers for talking to MySQL and PostgreSQL.

I use plain cursors here instead of pandas to_sql / read_sql. to_sql kept
breaking because of the pandas / SQLAlchemy versions inside the Airflow image,
and plain cursors work the same for MySQL and Postgres.
"""
from __future__ import annotations

import io
import logging
import math
from contextlib import suppress

from typing import Sequence

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def _native(value):
    """numpy/pandas values -> normal python values, the db drivers don't like numpy types"""
    if value is None:
        return None
    with suppress(TypeError, ValueError):
        if pd.isna(value):          # NaN, NaT and pd.NA all become NULL
            return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        value = value.item()
        if isinstance(value, float) and math.isnan(value):
            return None
    return value


def df_to_rows(df: pd.DataFrame) -> list[tuple]:
    obj = df.astype(object)
    return [tuple(_native(v) for v in row) for row in obj.itertuples(index=False, name=None)]


def execute_script(conn, sql_text: str) -> None:
    """run a sql script one statement at a time (split on ;)"""
    cur = conn.cursor()
    for stmt in (s.strip() for s in sql_text.split(";")):
        if stmt:
            cur.execute(stmt)
    conn.commit()
    cur.close()


def fetch_df(conn, sql: str, params: Sequence | None = None) -> pd.DataFrame:
    """Run a query and return a DataFrame.

    dtype=object on purpose: otherwise an int column with NULLs turns into
    floats (7 -> 7.0) and Postgres COPY rejects it.
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame([tuple(r) for r in rows], columns=cols, dtype=object)


def fetch_scalar(conn, sql: str, params: Sequence | None = None):
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def insert_df(conn, table: str, df: pd.DataFrame, chunk_size: int = 5_000, commit: bool = True) -> int:
    """insert a DataFrame in batches. the column names have to match the table"""
    if df.empty:
        return 0
    cols = list(df.columns)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
    rows = df_to_rows(df)
    cur = conn.cursor()
    for start in range(0, len(rows), chunk_size):
        cur.executemany(sql, rows[start:start + chunk_size])
    cur.close()
    if commit:
        conn.commit()
    log.info("Inserted %s rows into %s", len(rows), table)
    return len(rows)


def pg_copy_df(cursor, table: str, df: pd.DataFrame) -> int:
    """load a DataFrame into Postgres with COPY, much faster than inserts"""
    if df.empty:
        return 0
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cols = ", ".join(df.columns)
    cursor.copy_expert(
        f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf
    )
    return len(df)
