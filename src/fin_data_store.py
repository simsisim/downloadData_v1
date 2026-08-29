"""
SQLite persistence for the financial-data snapshots and the CANSLIM screen.

    data/fin_data/fin_data.db
      financials(ticker, snapshot_date, <every fin_data column>)
          PRIMARY KEY (ticker, snapshot_date)
      canslim_screen(ticker, snapshot_date, preset, <every canslim_* column>)
          PRIMARY KEY (ticker, snapshot_date, preset)

Why a DB and not just the CSVs: one dated row per ticker per run accumulates a
history the flat CSVs throw away. That history is what O'Neil's "I" actually
needs (rising institutional-holder count quarter over quarter — unavailable from
a single yfinance snapshot) and what makes threshold back-testing possible.

The DB is the archive / query surface; the CSV exports
(financial_data_<choice>.csv, canslim_metrics_<choice>.csv,
canslim_screened_<choice>.csv) stay the interchange format.

The .db file itself is git-ignored; this module + the backfill entry point are
the committed, reproducible part.
"""
from __future__ import annotations

import glob
import os
import re
import sqlite3

import pandas as pd

from src.config import PARAMS_DIR

DB_PATH = os.path.join(PARAMS_DIR["FIN_DATA_DIR"], "fin_data.db")

FINANCIALS_TABLE = "financials"
SCREEN_TABLE = "canslim_screen"

# SQLite identifier hygiene — fin_data column names are snake/camelCase, but be
# defensive about anything odd sneaking in from a future yfinance field.
_SAFE_COL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def open_db(path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    bad = [c for c in df.columns if not _SAFE_COL.match(str(c))]
    if bad:
        df = df.rename(columns={c: re.sub(r"[^A-Za-z0-9_]", "_", str(c)) for c in bad})
    return df


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _ensure_columns(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    """ADD COLUMN for any df column the table doesn't have yet (schema drift)."""
    if not _table_exists(conn, table):
        return
    have = _existing_columns(conn, table)
    for col in df.columns:
        if col not in have:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}"')


def _delete_rows(conn: sqlite3.Connection, table: str, where: str, params: tuple) -> None:
    if _table_exists(conn, table):
        conn.execute(f'DELETE FROM "{table}" WHERE {where}', params)


def write_snapshot(df: pd.DataFrame, snapshot_date, conn: sqlite3.Connection | None = None) -> int:
    """
    Upsert one run's financial data as the snapshot for `snapshot_date`
    (YYYY-MM-DD). Idempotent: an existing snapshot for that date is replaced.
    Returns the row count written.
    """
    own = conn is None
    conn = conn or open_db()
    try:
        d = _sanitize_columns(df.copy())
        d["snapshot_date"] = str(snapshot_date)
        if "ticker" not in d.columns:
            raise ValueError("write_snapshot: DataFrame needs a 'ticker' column")
        d = d.drop_duplicates(subset=["ticker", "snapshot_date"], keep="last")
        _ensure_columns(conn, FINANCIALS_TABLE, d)
        _delete_rows(conn, FINANCIALS_TABLE, "snapshot_date = ?", (str(snapshot_date),))
        d.to_sql(FINANCIALS_TABLE, conn, if_exists="append", index=False)
        _add_pk_index(conn, FINANCIALS_TABLE, ("ticker", "snapshot_date"))
        conn.commit()
        return len(d)
    finally:
        if own:
            conn.close()


def write_screen(df: pd.DataFrame, snapshot_date, preset: str,
                 conn: sqlite3.Connection | None = None) -> int:
    """Upsert the CANSLIM screen output for (snapshot_date, preset)."""
    own = conn is None
    conn = conn or open_db()
    try:
        d = _sanitize_columns(df.copy())
        d["snapshot_date"] = str(snapshot_date)
        d["preset"] = str(preset)
        d = d.drop_duplicates(subset=["ticker", "snapshot_date", "preset"], keep="last")
        _ensure_columns(conn, SCREEN_TABLE, d)
        _delete_rows(conn, SCREEN_TABLE, "snapshot_date = ? AND preset = ?",
                     (str(snapshot_date), str(preset)))
        d.to_sql(SCREEN_TABLE, conn, if_exists="append", index=False)
        _add_pk_index(conn, SCREEN_TABLE, ("ticker", "snapshot_date", "preset"))
        conn.commit()
        return len(d)
    finally:
        if own:
            conn.close()


def _add_pk_index(conn: sqlite3.Connection, table: str, cols: tuple[str, ...]) -> None:
    """
    A UNIQUE index standing in for a PK (can't declare one after the fact on a
    to_sql-created table). Keeps the (ticker, snapshot_date[, preset]) grain.
    """
    name = f"ux_{table}_{'_'.join(cols)}"
    collist = ", ".join(f'"{c}"' for c in cols)
    conn.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "{name}" ON "{table}" ({collist})')


def snapshot_dates(conn: sqlite3.Connection, table: str = FINANCIALS_TABLE) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [r[0] for r in conn.execute(
        f'SELECT DISTINCT snapshot_date FROM "{table}" ORDER BY snapshot_date')]


def snapshot(conn: sqlite3.Connection, snapshot_date: str,
             table: str = FINANCIALS_TABLE) -> pd.DataFrame | None:
    if not _table_exists(conn, table):
        return None
    return pd.read_sql_query(
        f'SELECT * FROM "{table}" WHERE snapshot_date = ?', conn, params=(snapshot_date,))


def latest_snapshot(conn: sqlite3.Connection,
                    table: str = FINANCIALS_TABLE) -> pd.DataFrame | None:
    dates = snapshot_dates(conn, table)
    return snapshot(conn, dates[-1], table) if dates else None


def history(conn: sqlite3.Connection, ticker: str,
            table: str = FINANCIALS_TABLE) -> pd.DataFrame | None:
    if not _table_exists(conn, table):
        return None
    return pd.read_sql_query(
        f'SELECT * FROM "{table}" WHERE ticker = ? ORDER BY snapshot_date',
        conn, params=(ticker,))


# --------------------------------------------------------------------------
# Backfill: seed the DB from whatever financial_data_<choice>.csv files exist,
# so there is an immediate history to work with. snapshot_date = the file's
# newest `last_updated`. Run once:
#   python -c "from src.fin_data_store import backfill_from_csvs as b; b()"
# --------------------------------------------------------------------------
_SKIP = ("summary", "screened", "metrics")


def _infer_snapshot_date(df: pd.DataFrame) -> str:
    if "last_updated" in df.columns:
        ts = pd.to_datetime(df["last_updated"], errors="coerce").max()
        if pd.notna(ts):
            return ts.date().isoformat()
    return pd.Timestamp.today().date().isoformat()


def backfill_from_csvs(fin_data_dir: str | None = None,
                       conn: sqlite3.Connection | None = None) -> None:
    fin_data_dir = fin_data_dir or PARAMS_DIR["FIN_DATA_DIR"]
    own = conn is None
    conn = conn or open_db()
    try:
        paths = sorted(glob.glob(os.path.join(fin_data_dir, "financial_data_*.csv")))
        paths = [p for p in paths if not any(s in os.path.basename(p) for s in _SKIP)]
        if not paths:
            print(f"backfill: no financial_data_*.csv under {fin_data_dir}")
            return
        for p in paths:
            df = pd.read_csv(p, low_memory=False)
            if "ticker" not in df.columns:
                print(f"backfill: {os.path.basename(p)} has no 'ticker' column, skipped")
                continue
            snap = _infer_snapshot_date(df)
            n = write_snapshot(df, snap, conn=conn)
            print(f"backfill: {os.path.basename(p)} -> snapshot {snap} ({n} rows)")
        print(f"backfill: snapshots now in DB: {snapshot_dates(conn)}")
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    backfill_from_csvs()
