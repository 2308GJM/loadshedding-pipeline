# Analysis: Load-Shedding and Weather Correlation

## Research question

Does load-shedding stage or outage timing correlate with weather
conditions, time of day, or day of week?

## What the data currently shows

At time of writing, the enriched dataset contains two independent
pipeline runs — one manual, one via a fully automated Airflow DAG run
— each producing events via EskomSePush's `test` mode (used during
development since national load-shedding stage was 0 for the
duration of this project — see `docs/decisions.md`).

| Run date   | Events | Stage | Avg temp | Notes |
|------------|--------|-------|----------|-------|
| 2026-08-23 | 3      | 8     | 25.0°C   | Manual run |
| 2026-09-15 | 3      | 8     | 20.7°C   | Automated DAG run |

Both runs show the same pattern: three schedule IDs for the same area
(Sandown, Johannesburg) reporting an outage within the same minute of
each other, matched to a single weather reading each time, well inside
the 90-minute join tolerance (average 29 minutes across observed
matches).

One nuance worth being explicit about: `test` mode returns an event
timestamped at the moment of the API call, not the pipeline's nominal
`execution_date` — so the 2026-09-15 run's events are actually
timestamped 2026-09-16 internally. This is expected behavior of
EskomSePush's test data, not a pipeline bug, but it does mean
`event_start` in this dataset reflects fetch time rather than a
genuine historical outage time.

## Honest limitation

With events clustered around a single timestamp, this dataset cannot
support a genuine correlation claim — there isn't enough variation in
either the outage timing or the weather conditions observed to say
whether stage, hour of day, or temperature relate to one another in
any real sense. This is a direct consequence of developing against
`test` mode data during a period of no active load-shedding, not a
flaw in the pipeline's design.

## Honest limitation

With events clustered around a single timestamp, this dataset cannot
support a genuine correlation claim — there isn't enough variation in
either the outage timing or the weather conditions observed to say
whether stage, hour of day, or temperature relate to one another in
any real sense. This is a direct consequence of developing against
`test` mode data during a period of no active load-shedding, not a
flaw in the pipeline's design.
