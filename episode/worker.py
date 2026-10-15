"""Single-process owner for durable jobs. flock releases on crash."""

import fcntl, json, time, signal
from .storage import *
from .service import import_source, verify_version


def durable_connect(once=False):
    while True:
        try:
            return connect()
        except RuntimeError:
            if once:
                raise
            time.sleep(1)


def run(once=False):
    with (root() / "runtime/worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another Episode worker owns this storage")
        with durable_connect(once) as db:
            db.execute(
                "UPDATE jobs SET state='interrupted',stage='interrupted',error='Worker stopped before completion; retry is safe',updated=? WHERE state='running'",
                (now(),),
            )
        while True:
            with durable_connect(once) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1"
                ).fetchone()
                if row:
                    db.execute(
                        "UPDATE jobs SET state='running',updated=? WHERE id=?",
                        (now(), row["id"]),
                    )
            if not row:
                if once:
                    return
                time.sleep(0.5)
                continue
            try:
                args = json.loads(row["args"])
                if row["kind"] == "analyze":
                    from .analysis import supervise

                    supervise(row["id"])
                elif row["kind"] == "import":
                    import_source(row["id"], args.get("limit", 50))
                elif row["kind"] == "verify":
                    verify_version(args["version"], row["id"])
                else:
                    raise ValueError("Unknown job kind")
                state = "succeeded"
                error = None
            except InterruptedError as e:
                state = "cancelled"
                error = str(e)
            except Exception as e:
                state = "failed"
                error = str(e)
            with durable_connect(once) as db:
                db.execute(
                    "UPDATE jobs SET state=?,stage=?,error=?,updated=? WHERE id=?",
                    (state, state, error, now(), row["id"]),
                )
            if once:
                return


if __name__ == "__main__":
    run()
