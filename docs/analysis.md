# Analysis: Load-Shedding and Weather Correlation

## Research question

Does load-shedding stage or outage timing correlate with weather
conditions, time of day, or day of week?

## What the data currently shows

At time of writing, the enriched dataset contains a small number of
real events, produced by EskomSePush's `test` mode (used during
development since national load-shedding stage was 0 for the
duration of this project — see `docs/decisions.md`). All observed
events:

- Occurred at Stage 8
- Started within the same minute of each other, across three
  different schedule IDs for the same area (Sandown, Johannesburg)
- Matched to a single weather reading: ~25-26°C, clear conditions,
  no precipitation
- Matched within an average of 29 minutes of the nearest hourly
  weather reading, well inside the 90-minute tolerance window
