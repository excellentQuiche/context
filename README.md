# Context — local DuckDB edition

A small local web application for finding unusual NBA statistical windows. The browser contains no hard-coded player results: FastAPI queries a normalized DuckDB database and returns the summary, game chart, and comparable players together.

## What you need

- Python 3.11 or newer
- A **populated** `nba.duckdb` from the Wyatt Walsh NBA dataset
- Windows PowerShell, macOS Terminal, or a Linux shell

The 12 KB `nba.duckdb` included in the Kaggle download you tested is empty. Do not use it. A populated warehouse will be much larger and `scripts/inspect_database.py` will report tables with nonzero row counts.

## 1. Open the project

Extract this archive, open PowerShell in the extracted `context` folder, and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. Add the source database

Create this path and place the populated file there:

```text
context/
  data/
    source/
      nba.duckdb
```

Source data are ignored by Git, so you will not accidentally commit a multi-gigabyte database.

## 3. Inspect its real tables

```powershell
python scripts/inspect_database.py data/source/nba.duckdb
```

Look for one of these nonempty tables:

1. `analytics_player_game_complete` — preferred
2. `fact_player_game_traditional`
3. `fact_player_game_log`

The command prints each candidate's exact columns and row count.

## 4. Map the source schema

Open `integration.json`. Its default assumes `analytics_player_game_complete` and these common fields:

```json
{
  "source_table": "analytics_player_game_complete",
  "fields": {
    "player_id": "player_id",
    "player_name": "player_name",
    "game_id": "game_id",
    "game_date": "game_date",
    "season_year": "season_year",
    "season_type": "season_type",
    "team_id": "team_id",
    "team_abbreviation": "team_abbreviation",
    "opponent": "matchup",
    "minutes": "min",
    "pts": "pts",
    "reb": "reb",
    "ast": "ast"
  }
}
```

Change only the values on the right to match the columns printed by the inspection command. Use `null` for optional fields that do not exist. The required fields are:

- `player_id`
- `player_name`
- `game_id`
- `game_date`
- `season_year`
- `season_type`
- `minutes`
- `pts`

If your player-game fact does not contain player names, use the prejoined analytics view. Do not manually join the SCD2 `dim_player` table until you account for its `valid_from`, `valid_to`, and `is_current` fields; a naive join can duplicate historical games.

## 5. Build the application database

```powershell
python scripts/build_database.py data/source/nba.duckdb
```

Successful output looks like:

```text
Built .../data/app/context.duckdb
1,234,567 player-games | 5,000 players | 78 seasons (1946-47 to 2025-26)
```

The builder:

- reads the source database without modifying it;
- converts `MM:SS` minutes to decimal minutes;
- removes duplicate `(player_id, game_id)` rows deterministically;
- preserves regular-season/playoff labels;
- creates query indexes;
- refuses an empty placeholder database;
- writes only the columns Context needs.

## 6. Run Context

Windows:

```powershell
.\run.ps1
```

macOS/Linux:

```bash
chmod +x run.sh
./run.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The season selector, player selector, summary, game chart, and similar-results table all query the same database. Clicking a table row loads that player.

## How rolling windows are calculated

Games are ordered by `game_date, game_id` within each player, season, and season type. A two-game window means two consecutive player appearances, not two calendar days and not two team games. Incomplete windows are excluded. Ties use the earliest ending date.

This definition is intentional and reproducible. If you want team-calendar windows that count missed games, add the team schedule and explicitly left-join player appearances.

## Updating the data

When you download a newer warehouse version:

1. Stop the server.
2. Replace `data/source/nba.duckdb`.
3. Run the inspection command once to catch schema changes.
4. Update `integration.json` only if columns changed.
5. Run `build_database.py` again.
6. Restart the server.

The application database is rebuilt from the source. Do not append new warehouse rows by hand.

## Using CSV files instead

The legacy `game.csv` is team-level and `player.csv` is only an identity list. They cannot produce player rolling windows. You need a player-game CSV such as an export of `analytics_player_game_complete`.

Export it from DuckDB:

```sql
COPY (
  SELECT player_id, player_name, game_id, game_date, season_year,
         season_type, team_id, team_abbreviation, matchup, min, pts, reb, ast
  FROM analytics_player_game_complete
) TO 'player_games.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
```

Parquet is preferable to CSV because it preserves types and is much smaller. The supplied builder currently reads a DuckDB warehouse; add a Parquet ingestion branch only if you decide to distribute the normalized extract separately.

## Accuracy checklist

Before trusting a result, verify:

- source table row count is nonzero;
- season labels are correct;
- preseason, All-Star, and playoffs are not mixed with regular season;
- `(player_id, game_id)` is unique after normalization;
- minutes parse correctly;
- DNP rows are absent or explicitly handled;
- one known player/season agrees with an NBA reference;
- the UI's selected game IDs reproduce the displayed average in SQL.

## Useful SQL checks

```sql
-- Duplicates should return no rows
SELECT player_id, game_id, count(*)
FROM player_games
GROUP BY 1, 2
HAVING count(*) > 1;

-- Coverage
SELECT season_year, season_type, count(*) AS player_games
FROM player_games
GROUP BY 1, 2
ORDER BY 1, 2;

-- Basic plausibility
SELECT min(game_date), max(game_date), min(minutes), max(minutes), max(pts)
FROM player_games;
```

## Project structure

```text
app/main.py                 FastAPI routes and DuckDB queries
app/static/index.html       Dashboard markup
app/static/style.css        Visual design
app/static/app.js           Browser behavior
scripts/inspect_database.py Schema inspection
scripts/build_database.py   Source normalization
integration.json            Explicit source-column mapping
data/source/                Your source warehouse; not committed
data/app/                   Generated application DB; not committed
```
