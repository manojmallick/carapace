"""Single memory read, used in a loop by scripts/shell-test.sh.

Prints one line: OK/FAIL, latency, and which gateway node served the
read -- so the Shell Test log shows traffic actually moving to the
surviving nodes when one dies.
"""

import sys
import time

import psycopg

from . import config


def probe() -> int:
    t0 = time.time()
    try:
        with psycopg.connect(config.DB_READ_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                # allow_unsafe_internals: only to report which gateway
                # node served the read, so the Shell Test log shows
                # traffic moving to the survivors. Not used by the app.
                cur.execute("SET allow_unsafe_internals = true")
                cur.execute(
                    "SELECT count(*), crdb_internal.node_id()::STRING FROM semantic_cache GROUP BY 2"
                )
                row = cur.fetchone()
        ms = (time.time() - t0) * 1000
        rows, node = (row if row else (0, "?"))
        print(f"OK   {ms:7.1f}ms  rows={rows}  via_node={node}")
        return 0
    except Exception as exc:  # noqa: BLE001
        ms = (time.time() - t0) * 1000
        print(f"FAIL {ms:7.1f}ms  {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(probe())
