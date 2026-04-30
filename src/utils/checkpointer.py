"""SQLite checkpointer management for persistent LangGraph state."""

import sqlite3
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.constants import DOCSPATCH_DIR
from src.utils.config import load
from src.utils.log import get_logger
from src.utils.ui import warn

logger = get_logger(__name__)

DB_PATH = DOCSPATCH_DIR / "checkpoints.db"
DB_WARN_MB = 50


async def get_checkpointer() -> tuple[AbstractAsyncContextManager[AsyncSqliteSaver], JsonPlusSerializer]:
    """Initialize and return a context manager for the SQLite checkpoint store.

    Sets up the checkpoint directory and initializes a context manager for
    saving/loading checkpoint data to an SQLite database."""
    DOCSPATCH_DIR.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        size_mb = DB_PATH.stat().st_size / (1024 * 1024)
        if size_mb > DB_WARN_MB:
            warn(f"Checkpoint DB is {size_mb:.1f} MB. Run `dp cleanup` to reclaim space.")

    # Prune stale threads and VACUUM using a temporary sync connection
    conn = sqlite3.connect(str(DB_PATH))
    deleted = prune_old_threads(conn, load().defaults.prune_after_days)
    if deleted > 0:
        conn.execute("VACUUM")
        logger.debug("Pruned %d stale checkpoint threads and vacuumed DB", deleted)
    conn.close()

    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("src.schemas.function", "FunctionMetadata"),
            ("src.schemas.state", "DocpatchState"),
        ]
    )

    return (AsyncSqliteSaver.from_conn_string(str(DB_PATH)), serde)


def prune_old_threads(conn: sqlite3.Connection, prune_after_days: int) -> int:
    """Delete checkpoint threads older than the configured expiration."""
    cutoff = (datetime.now() - timedelta(days=prune_after_days)).strftime("%Y%m%d%H%M%S")
    try:
        cur = conn.execute(
            """DELETE FROM checkpoints 
            WHERE INSTR(thread_id, '_') = 17 AND SUBSTR(thread_id, 18) < ?""",
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount
    except sqlite3.OperationalError:
        return 0
