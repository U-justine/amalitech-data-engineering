"""File watermark, so the pipeline doesn't load the same file twice.

After a run has loaded and checked everything, I save the md5 of the csv in
analytics.pipeline_watermark. The next run compares the md5 of the file in
data/ with the saved one:
  - same md5      -> the data didn't change, skip the run
  - different md5 -> new data, run everything
  - no watermark  -> first run, run everything
force_full_reload=True runs everything anyway (e.g. after I changed the code).

The watermark is only saved at the very end, after verify_postgres_load, so
a failed run never marks a file as done.
"""
from __future__ import annotations

import logging

from . import db
from .schema import PG_SCHEMA

log = logging.getLogger(__name__)

TABLE = f"{PG_SCHEMA}.pipeline_watermark"


def should_run(file_md5: str, stored: dict | None, force: bool = False) -> tuple[bool, str]:
    """decide if the run should go ahead. returns (run?, reason for the log)"""
    if force:
        return True, "force_full_reload is on, running everything"
    if not stored:
        return True, "no watermark yet (first run), running everything"
    if stored.get("file_md5") == file_md5:
        return False, (f"same file as the last load (md5 {file_md5[:12]}..., loaded by "
                       f"{stored.get('batch_id')} at {stored.get('updated_at')}), skipping")
    return True, f"file changed (md5 {str(stored.get('file_md5'))[:12]}... -> {file_md5[:12]}...), running everything"


def get(pg_conn, pipeline: str) -> dict | None:
    """last saved watermark, or None if there isn't one (or the table doesn't exist yet)"""
    exists = db.fetch_scalar(pg_conn, "SELECT to_regclass(%s)", (TABLE,))
    if not exists:
        return None
    df = db.fetch_df(pg_conn, f"SELECT pipeline, source_file, file_md5, file_bytes, rows_loaded, batch_id, updated_at "
                              f"FROM {TABLE} WHERE pipeline = %s", (pipeline,))
    return None if df.empty else df.iloc[0].to_dict()


def save(pg_conn, pipeline: str, file_info: dict, rows_loaded: int, batch_id: str) -> dict:
    """save (or replace) the watermark after a good run"""
    cur = pg_conn.cursor()
    try:
        cur.execute(
            f"""INSERT INTO {TABLE} (pipeline, source_file, file_md5, file_bytes, rows_loaded, batch_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (pipeline) DO UPDATE SET
                    source_file = EXCLUDED.source_file, file_md5 = EXCLUDED.file_md5,
                    file_bytes = EXCLUDED.file_bytes, rows_loaded = EXCLUDED.rows_loaded,
                    batch_id = EXCLUDED.batch_id, updated_at = now()""",
            (pipeline, file_info["path"], file_info["md5"], file_info["bytes"], rows_loaded, batch_id),
        )
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        cur.close()
    log.info("Watermark saved: %s md5=%s rows=%s", pipeline, file_info["md5"], rows_loaded)
    return {"pipeline": pipeline, "file_md5": file_info["md5"], "rows_loaded": rows_loaded, "batch_id": batch_id}
