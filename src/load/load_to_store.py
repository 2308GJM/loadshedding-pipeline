"""
Load the enriched gold-layer dataset into the serving store (Postgres).

Writes are idempotent per execution_date: re-running this task for a given
day upserts rather than appends, so DAG retries don't create duplicate rows.
"""


def run(execution_date: str):
    raise NotImplementedError("Wire up Postgres load (upsert by execution_date) here")
