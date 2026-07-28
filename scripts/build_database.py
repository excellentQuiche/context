import argparse
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "source" / "PlayerStatistics.csv"
DEFAULT_TARGET = ROOT / "data" / "app" / "context.duckdb"

parser = argparse.ArgumentParser()
parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
args = parser.parse_args()

source = args.source.resolve()
target = args.target.resolve()

if not source.exists():
    raise SystemExit(f"Source file not found: {source}")

target.parent.mkdir(parents=True, exist_ok=True)
target.unlink(missing_ok=True)

source_path = str(source).replace("'", "''")
db = duckdb.connect(str(target))

db.execute(f"""
CREATE TABLE player_games AS
WITH raw AS (
    SELECT *
    FROM read_csv_auto(
        '{source_path}',
        header=true,
        all_varchar=true,
        sample_size=-1
    )
),
parsed AS (
    SELECT
        try_cast(personId AS BIGINT) AS player_id,
        trim(concat_ws(
            ' ',
            nullif(trim(firstName), ''),
            nullif(trim(lastName), '')
        )) AS player_name,
        cast(gameId AS VARCHAR) AS game_id,
        coalesce(
            try_cast(gameDate AS TIMESTAMP),
            try_cast(gameDateTimeEst AS TIMESTAMP)
        ) AS game_datetime,
        trim(gameType) AS source_game_type,
        trim(gameLabel) AS game_label,
        trim(gameSubLabel) AS game_sub_label,
        try_cast(seriesGameNumber AS INTEGER) AS series_game_number,
        try_cast(playerteamId AS BIGINT) AS team_id,
        trim(concat_ws(
            ' ',
            nullif(trim(playerteamCity), ''),
            nullif(trim(playerteamName), '')
        )) AS team_name,
        try_cast(opponentteamId AS BIGINT) AS opponent_id,
        trim(concat_ws(
            ' ',
            nullif(trim(opponentteamCity), ''),
            nullif(trim(opponentteamName), '')
        )) AS opponent,
        CASE
            WHEN lower(trim(home)) IN ('1', 'true', 't', 'yes') THEN true
            WHEN lower(trim(home)) IN ('0', 'false', 'f', 'no') THEN false
            ELSE NULL
        END AS home,
        CASE
            WHEN lower(trim(win)) IN ('1', 'true', 't', 'yes') THEN true
            WHEN lower(trim(win)) IN ('0', 'false', 'f', 'no') THEN false
            ELSE NULL
        END AS win,
        try_cast(numMinutes AS DOUBLE) AS minutes,
        nullif(trim(startingPosition), '') AS starting_position,
        try_cast(points AS DOUBLE) AS pts,
        try_cast(reboundsTotal AS DOUBLE) AS reb,
        try_cast(assists AS DOUBLE) AS ast,
        try_cast(steals AS DOUBLE) AS stl,
        try_cast(blocks AS DOUBLE) AS blk,
        try_cast(turnovers AS DOUBLE) AS tov,
        try_cast(foulsPersonal AS DOUBLE) AS pf,
        try_cast(fieldGoalsMade AS DOUBLE) AS fgm,
        try_cast(fieldGoalsAttempted AS DOUBLE) AS fga,
        try_cast(fieldGoalsPercentage AS DOUBLE) AS fg_pct,
        try_cast(threePointersMade AS DOUBLE) AS fg3m,
        try_cast(threePointersAttempted AS DOUBLE) AS fg3a,
        try_cast(threePointersPercentage AS DOUBLE) AS fg3_pct,
        try_cast(freeThrowsMade AS DOUBLE) AS ftm,
        try_cast(freeThrowsAttempted AS DOUBLE) AS fta,
        try_cast(freeThrowsPercentage AS DOUBLE) AS ft_pct,
        try_cast(reboundsOffensive AS DOUBLE) AS oreb,
        try_cast(reboundsDefensive AS DOUBLE) AS dreb,
        try_cast(plusMinusPoints AS DOUBLE) AS plus_minus,
        trim(comment) AS comment
    FROM raw
),
normalized AS (
    SELECT
        *,
        cast(game_datetime AS DATE) AS game_date,
        CASE
            WHEN extract(month FROM game_datetime) >= 7
                THEN cast(extract(year FROM game_datetime) AS INTEGER)
            ELSE cast(extract(year FROM game_datetime) AS INTEGER) - 1
        END AS season_start,
        CASE
            WHEN lower(coalesce(game_label, '')) LIKE '%cup%'
                 AND lower(coalesce(game_sub_label, '')) = 'championship'
                THEN 'NBA Cup Championship'
            WHEN source_game_type IN (
                'NBA Cup',
                'Emirates NBA Cup',
                'in-season-knockout'
            )
                THEN 'NBA Cup Championship'
            WHEN source_game_type = 'NBA Emirates Cup'
                THEN 'Regular Season'
            WHEN source_game_type = 'Regular Season'
                THEN 'Regular Season'
            WHEN source_game_type = 'Playoffs'
                THEN 'Playoffs'
            WHEN source_game_type = 'Play-in Tournament'
                THEN 'Play-In'
            WHEN source_game_type IN ('Preseason', 'Pre Season')
                THEN 'Preseason'
            WHEN source_game_type = 'All-Star Game'
                THEN 'All-Star'
            ELSE 'Other'
        END AS season_type
    FROM parsed
)
SELECT
    player_id,
    player_name,
    game_id,
    game_date,
    game_datetime,
    printf(
        '%04d-%02d',
        season_start,
        (season_start + 1) % 100
    ) AS season_year,
    season_type,
    source_game_type,
    game_label,
    game_sub_label,
    series_game_number,
    team_id,
    team_name,
    cast(NULL AS VARCHAR) AS team_abbreviation,
    opponent_id,
    opponent,
    home,
    win,
    minutes,
    starting_position IS NOT NULL AS started,
    starting_position,
    pts,
    reb,
    ast,
    stl,
    blk,
    tov,
    pf,
    fgm,
    fga,
    fg_pct,
    fg3m,
    fg3a,
    fg3_pct,
    ftm,
    fta,
    ft_pct,
    oreb,
    dreb,
    plus_minus,
    comment
FROM normalized
WHERE player_id IS NOT NULL
  AND game_id IS NOT NULL
  AND trim(game_id) <> ''
  AND game_datetime IS NOT NULL
  AND player_name <> ''
  AND minutes > 0
  AND minutes <= 80
  AND upper(coalesce(comment, '')) NOT LIKE 'DNP%'
  AND upper(coalesce(comment, '')) NOT LIKE 'DND%'
  AND upper(coalesce(comment, '')) NOT LIKE 'NWT%'
  AND pts IS NOT NULL
  AND reb IS NOT NULL
  AND ast IS NOT NULL
QUALIFY row_number() OVER (
    PARTITION BY player_id, game_id
    ORDER BY game_datetime, player_name
) = 1
""")

db.execute("""
CREATE INDEX player_season_idx
ON player_games(season_year, season_type, player_id)
""")

db.execute("""
CREATE INDEX player_date_idx
ON player_games(player_id, game_date)
""")

db.execute("""
CREATE INDEX game_idx
ON player_games(game_id)
""")

db.execute("""
CREATE TABLE app_metadata (
    key VARCHAR PRIMARY KEY,
    value VARCHAR
)
""")

db.execute(
    """
    INSERT INTO app_metadata
    VALUES
        ('built_at', ?),
        ('source', ?)
    """,
    [
        datetime.now(timezone.utc).isoformat(),
        str(source),
    ],
)

rows = db.execute("""
    SELECT count(*)
    FROM player_games
""").fetchone()[0]

players = db.execute("""
    SELECT count(DISTINCT player_id)
    FROM player_games
""").fetchone()[0]

games = db.execute("""
    SELECT count(DISTINCT game_id)
    FROM player_games
""").fetchone()[0]

coverage = db.execute("""
    SELECT
        min(game_date),
        max(game_date),
        count(DISTINCT season_year)
    FROM player_games
""").fetchone()

duplicates = db.execute("""
    SELECT count(*)
    FROM (
        SELECT player_id, game_id
        FROM player_games
        GROUP BY player_id, game_id
        HAVING count(*) > 1
    )
""").fetchone()[0]

if rows == 0:
    raise SystemExit("The build produced zero player-game rows.")

if duplicates:
    raise SystemExit(f"The build produced {duplicates} duplicate player-game pairs.")

print(f"Built {target}")
print(f"{rows:,} player-games")
print(f"{players:,} players")
print(f"{games:,} games")
print(f"{coverage[2]} seasons")
print(f"{coverage[0]} to {coverage[1]}")

print("\nSeason types")
for row in db.execute("""
    SELECT season_type, count(*)
    FROM player_games
    GROUP BY season_type
    ORDER BY count(*) DESC
""").fetchall():
    print(row)

db.close()
