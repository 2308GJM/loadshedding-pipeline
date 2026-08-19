"""
Join validated load-shedding records to validated weather records by
nearest timestamp, within a tolerance window.

Design contract (see docs/decisions.md):
  - for each load-shedding event, find the weather reading with the
    closest timestamp to the event's start_time
  - if no weather reading exists within JOIN_TOLERANCE, the event is
    logged as unmatched and excluded from the enriched output — never
    silently joined to the nearest reading regardless of distance
  - the join key is (area's approximate lat/lon bucket, nearest hour)
"""
from datetime import timedelta

JOIN_TOLERANCE = timedelta(hours=1)


def run(execution_date: str):
    """
    Loads the silver-layer load-shedding and weather outputs for
    execution_date, performs the nearest-timestamp join, and writes the
    enriched gold-layer output plus an unmatched-events log.
    """
    raise NotImplementedError("Wire up Spark join logic here")
