# NBAcontext

NBAcontext is a simple NBA stats dashboard that allows the user to compare players from different seasons, look for their best stretches of games, switch between totals and rate stats, and view game-by-game results.

A big part of the project is showing how things like sample size or the way a stat is calculated can make a comparison look more impressive than it really is.

**Live demo:** `https://context-cjvn.onrender.com/`

<img width="1880" height="307" alt="image" src="https://github.com/user-attachments/assets/ea51d9e6-11f3-47bc-bd6f-c1066efcb8be" />
<img width="1880" height="502" alt="image" src="https://github.com/user-attachments/assets/a3a3c212-2c69-43da-8346-6f804c17f562" />
<img width="1880" height="503" alt="image" src="https://github.com/user-attachments/assets/8274614b-976a-4adb-9f00-1b45be883039" />

## Features
- Compare players across different seasons
- Find a player's best 2–20 game stretch
- View full-season stats
- Switch between per-game, total, per-36, and per-100 stats
- Traditional and advanced NBA stats
- Weighted shooting percentages
- Intentionally misleading unweighted shooting averages for comparison
- Season leaderboards
- Search for players
- Game-by-game charts
- Player and team images

## Dataset contains:
- **1.39 million player-game rows**
- **5,280 players**
- **69,000+ games**
- **75 NBA seasons**
- Data going back to **1951–52**
- Advanced stats going back to **1996–97**

The data comes from this Kaggle dataset: https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores
Older box score data is used as the base, and advanced stats are added when they're available.

The finished DuckDB database is too large to keep in the Git repo, so production downloads a compressed copy from a GitHub Release during deployment.

## Tech Stack
- Python
- FastAPI
- DuckDB
- HTML (just for index)
- CSS
- Vanilla JS
- Render (for hosting, as mentioned)

Basic flow:

```text
Raw NBA CSV files
        ↓
Python data cleanup/build script
        ↓
      DuckDB
        ↓
    FastAPI API
        ↓
  Vanilla JS frontend
        ↓
Charts and comparisons
```

## Backend
The backend uses FastAPI for things like:

- Validating requests
- Defining metrics
- Aggregating stats
- Calculating rolling streaks
- Comparing seasons
- Player information
- Leaderboards

DuckDB stores the cleaned player-game data and handles most of the analytics queries.

## Frontend

The frontend is plain HTML, CSS, and JavaScript.

It handles:
- Player search
- Season selection
- Metric selection
- Player comparisons
- Game-by-game charts
- Leaderboards
- Responsive UI controls
- Player/team image fallbacks

I kept it framework-free because the frontend is fairly small and I wanted to work directly with JavaScript and the API.

## Data Pipeline
`scripts/build_database.py` builds the DuckDB database from the raw datasets.

It:
1. Loads the player-game data
2. Cleans IDs, dates, seasons, minutes, and game types
3. Removes invalid/non-participation rows
4. Removes duplicate player/game records
5. Joins advanced stats when available
6. Creates indexes for common queries
7. Runs a few checks on the finished data

Advanced stats fail to load & are caught for older seasons where they don't exist in the Kaggle set. 

## Stats
For counting stats, the app supports:
- Per game
- Total
- Per 36 minutes (most common rate stat/measure of efficiency)
- Per 100 possessions

For shooting percentages, I added two calculation methods.

The normal option uses the correct weighted percentage. There's also an intentionally misleading option that averages each game's percentage equally.

That second option is mainly there to show how a technically calculated number can give a misleading result.

Rolling streaks are based on consecutive games a player appeared in during a regular season, or postseason if selected. The default is regular season though. 

## API
FastAPI's built-in API docs are available at:

```text
/docs
```

Main endpoints:
```text
GET /api/meta
GET /api/metrics
GET /api/players
GET /api/all-players
GET /api/result
GET /api/compare
GET /api/similar
```

## Running Locally

Requires Python 3.12+.

```bash
git clone <REPOSITORY_URL>
cd nbacontext

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The database isn't included in the repo.

Put the source datasets in `data/source/`, then build the database:

```bash
python scripts/build_database.py

## Project Structure

```text
app/
  main.py
  metrics.py
  static/
    index.html
    style.css
    app.js
    search.js

data/
  source/
  app/

scripts/
  build_database.py
  download_database.py
  inspect_database.py

tests/

.github/
  workflows/
    ci.yml

render.yaml
requirements.txt
run.sh
```
````
