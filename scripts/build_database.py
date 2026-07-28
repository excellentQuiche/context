import argparse
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "source" / "PlayerStatistics.csv"
DEFAULT_EXTENDED = ROOT / "data" / "source" / "PlayerStatisticsExtended.csv"
DEFAULT_PLAYERS = ROOT / "data" / "source" / "Players.csv"
DEFAULT_TARGET = ROOT / "data" / "app" / "context.duckdb"

parser = argparse.ArgumentParser()
parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
parser.add_argument("--extended", type=Path, default=DEFAULT_EXTENDED)
parser.add_argument("--players", type=Path, default=DEFAULT_PLAYERS)
parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
args = parser.parse_args()

source = args.source.resolve()
extended_source = args.extended.resolve()
players_source = args.players.resolve()
target = args.target.resolve()

for path in (source, extended_source, players_source):
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")

target.parent.mkdir(parents=True, exist_ok=True)
target.unlink(missing_ok=True)

db = duckdb.connect(str(target))


def sql_path(path):
    return str(path).replace("'", "''")


def column(columns, name):
    return f'"{name}"' if name in columns else "NULL"


def text(columns, name):
    return f"nullif(trim(cast({column(columns, name)} AS VARCHAR)), '')"


def number(columns, name):
    return f"try_cast({column(columns, name)} AS DOUBLE)"


def integer(columns, name):
    return f"try_cast({column(columns, name)} AS INTEGER)"


db.execute(f"""
CREATE TEMP VIEW base_source AS
SELECT *
FROM read_csv_auto(
    '{sql_path(source)}',
    header=true,
    all_varchar=true,
    sample_size=-1
)
""")

db.execute(f"""
CREATE TEMP VIEW extended_source AS
SELECT *
FROM read_csv_auto(
    '{sql_path(extended_source)}',
    header=true,
    all_varchar=true,
    sample_size=-1
)
""")

base_columns = {
    row[0]
    for row in db.execute("DESCRIBE base_source").fetchall()
}

extended_columns = {
    row[0]
    for row in db.execute("DESCRIBE extended_source").fetchall()
}

required_base = {
    "personId",
    "gameId",
    "firstName",
    "lastName",
    "gameType",
    "numMinutes",
    "points",
    "assists",
    "reboundsTotal",
}

missing_base = sorted(required_base - base_columns)

if missing_base:
    raise SystemExit(
        f"Base source is missing columns: {', '.join(missing_base)}"
    )

traditional_fields = [
    ("points", "pts"),
    ("assists", "ast"),
    ("blocks", "blk"),
    ("steals", "stl"),
    ("fieldGoalsAttempted", "fga"),
    ("fieldGoalsMade", "fgm"),
    ("fieldGoalsPercentage", "fg_pct"),
    ("threePointersAttempted", "fg3a"),
    ("threePointersMade", "fg3m"),
    ("threePointersPercentage", "fg3_pct"),
    ("freeThrowsAttempted", "fta"),
    ("freeThrowsMade", "ftm"),
    ("freeThrowsPercentage", "ft_pct"),
    ("reboundsDefensive", "dreb"),
    ("reboundsOffensive", "oreb"),
    ("reboundsTotal", "reb"),
    ("foulsPersonal", "pf"),
    ("turnovers", "tov"),
    ("plusMinusPoints", "plus_minus"),
]

advanced_fields = [
    ("blocksAgainst", "blocks_against"),
    ("foulsAgainst", "fouls_against"),
    ("estimatedOffensiveRating", "estimated_offensive_rating"),
    ("offensiveRating", "offensive_rating"),
    ("spWorkOffensiveRating", "sp_work_offensive_rating"),
    ("estimatedDefensiveRating", "estimated_defensive_rating"),
    ("defensiveRating", "defensive_rating"),
    ("spWorkDefensiveRating", "sp_work_defensive_rating"),
    ("estimatedNetRating", "estimated_net_rating"),
    ("netRating", "net_rating"),
    ("spWorkNetRating", "sp_work_net_rating"),
    ("assistPercentage", "assist_percentage"),
    ("assistToTurnoverRatio", "assist_to_turnover_ratio"),
    ("assistRatio", "assist_ratio"),
    ("offensiveReboundPercentage", "offensive_rebound_percentage"),
    ("defensiveReboundPercentage", "defensive_rebound_percentage"),
    ("reboundPercentage", "rebound_percentage"),
    ("teamTurnoverPercentage", "team_turnover_percentage"),
    ("estimatedTurnoverPercentage", "estimated_turnover_percentage"),
    ("effectiveFieldGoalPercentage", "effective_field_goal_percentage"),
    ("trueShootingPercentage", "true_shooting_percentage"),
    ("usagePercentage", "usage_percentage"),
    ("estimatedUsagePercentage", "estimated_usage_percentage"),
    ("estimatedPace", "estimated_pace"),
    ("pace", "pace"),
    ("pacePer40", "pace_per_40"),
    ("spWorkPace", "sp_work_pace"),
    ("playerImpactEstimate", "player_impact_estimate"),
    ("possessions", "possessions"),
    ("pointsOffTurnovers", "points_off_turnovers"),
    ("pointsSecondChance", "points_second_chance"),
    ("pointsFastBreak", "points_fast_break"),
    ("pointsInPaint", "points_in_paint"),
    ("opponentPointsOffTurnovers", "opponent_points_off_turnovers"),
    ("opponentPointsSecondChance", "opponent_points_second_chance"),
    ("opponentPointsFastBreak", "opponent_points_fast_break"),
    ("opponentPointsInPaint", "opponent_points_in_paint"),
    ("percentFieldGoalAttempts2Point", "percent_field_goal_attempts_2_point"),
    ("percentFieldGoalAttempts3Point", "percent_field_goal_attempts_3_point"),
    ("percentPoints2Point", "percent_points_2_point"),
    ("percentPoints2PointMidRange", "percent_points_2_point_mid_range"),
    ("percentPoints3Point", "percent_points_3_point"),
    ("percentPointsFastBreak", "percent_points_fast_break"),
    ("percentPointsFreeThrow", "percent_points_free_throw"),
    ("percentPointsOffTurnovers", "percent_points_off_turnovers"),
    ("percentPointsInPaint", "percent_points_in_paint"),
    ("percentAssisted2PointMade", "percent_assisted_2_point_made"),
    ("percentUnassisted2PointMade", "percent_unassisted_2_point_made"),
    ("percentAssisted3PointMade", "percent_assisted_3_point_made"),
    ("percentUnassisted3PointMade", "percent_unassisted_3_point_made"),
    ("percentAssistedFieldGoalsMade", "percent_assisted_field_goals_made"),
    ("percentUnassistedFieldGoalsMade", "percent_unassisted_field_goals_made"),
    ("percentTeamFieldGoalsMade", "percent_team_field_goals_made"),
    ("percentTeamFieldGoalsAttempted", "percent_team_field_goals_attempted"),
    ("percentTeamThreePointersMade", "percent_team_three_pointers_made"),
    ("percentTeamThreePointersAttempted", "percent_team_three_pointers_attempted"),
    ("percentTeamFreeThrowsMade", "percent_team_free_throws_made"),
    ("percentTeamFreeThrowsAttempted", "percent_team_free_throws_attempted"),
    ("percentTeamOffensiveRebounds", "percent_team_offensive_rebounds"),
    ("percentTeamDefensiveRebounds", "percent_team_defensive_rebounds"),
    ("percentTeamRebounds", "percent_team_rebounds"),
    ("percentTeamAssists", "percent_team_assists"),
    ("percentTeamTurnovers", "percent_team_turnovers"),
    ("percentTeamSteals", "percent_team_steals"),
    ("percentTeamBlocks", "percent_team_blocks"),
    ("percentTeamBlocksAgainst", "percent_team_blocks_against"),
    ("percentTeamFoulsPersonal", "percent_team_fouls_personal"),
    ("percentTeamFoulsDrawn", "percent_team_fouls_drawn"),
    ("percentTeamPoints", "percent_team_points"),
]

advanced_integer_fields = [
    ("doubleDouble", "double_double"),
    ("tripleDouble", "triple_double"),
]

required_extended = {
    "personId",
    "gameId",
    *[source_name for source_name, _ in advanced_fields],
    *[source_name for source_name, _ in advanced_integer_fields],
}

missing_extended = sorted(required_extended - extended_columns)

if missing_extended:
    raise SystemExit(
        f"Extended source is missing columns: {', '.join(missing_extended)}"
    )

advanced_select = [
    f"try_cast({column(extended_columns, 'personId')} AS BIGINT) AS player_id",
    f"cast({column(extended_columns, 'gameId')} AS VARCHAR) AS game_id",
]

advanced_select.extend(
    f"{number(extended_columns, source_name)} AS {target_name}"
    for source_name, target_name in advanced_fields
)

advanced_select.extend(
    f"{integer(extended_columns, source_name)} AS {target_name}"
    for source_name, target_name in advanced_integer_fields
)

db.execute(f"""
CREATE TEMP TABLE advanced_games AS
SELECT
    {", ".join(advanced_select)}
FROM extended_source
WHERE try_cast(
        {column(extended_columns, 'personId')}
        AS BIGINT
      ) IS NOT NULL
  AND {column(extended_columns, 'gameId')} IS NOT NULL
QUALIFY row_number() OVER (
    PARTITION BY
        try_cast(
            {column(extended_columns, 'personId')}
            AS BIGINT
        ),
        cast(
            {column(extended_columns, 'gameId')}
            AS VARCHAR
        )
    ORDER BY
        try_cast(
            {column(extended_columns, 'personId')}
            AS BIGINT
        )
) = 1
""")

game_datetime = f"""
coalesce(
    try_cast({column(base_columns, 'gameDate')} AS TIMESTAMP),
    try_cast({column(base_columns, 'gameDateTimeEst')} AS TIMESTAMP)
)
"""

base_select = [
    f"try_cast({column(base_columns, 'personId')} AS BIGINT) AS player_id",
    f"trim(concat_ws(' ', {text(base_columns, 'firstName')}, {text(base_columns, 'lastName')})) AS player_name",
    f"cast({column(base_columns, 'gameId')} AS VARCHAR) AS game_id",
    f"{game_datetime} AS game_datetime",
    f"{text(base_columns, 'gameType')} AS source_game_type",
    f"{text(base_columns, 'gameLabel')} AS game_label",
    f"{text(base_columns, 'gameSubLabel')} AS game_sub_label",
    f"{integer(base_columns, 'seriesGameNumber')} AS series_game_number",
    f"try_cast({column(base_columns, 'playerteamId')} AS BIGINT) AS team_id",
    f"trim(concat_ws(' ', {text(base_columns, 'playerteamCity')}, {text(base_columns, 'playerteamName')})) AS team_name",
    f"try_cast({column(base_columns, 'opponentteamId')} AS BIGINT) AS opponent_id",
    f"trim(concat_ws(' ', {text(base_columns, 'opponentteamCity')}, {text(base_columns, 'opponentteamName')})) AS opponent",
    f"""
    CASE
        WHEN lower(trim(cast({column(base_columns, 'home')} AS VARCHAR)))
             IN ('1', 'true', 't', 'yes')
            THEN true
        WHEN lower(trim(cast({column(base_columns, 'home')} AS VARCHAR)))
             IN ('0', 'false', 'f', 'no')
            THEN false
        ELSE NULL
    END AS home
    """,
    f"""
    CASE
        WHEN lower(trim(cast({column(base_columns, 'win')} AS VARCHAR)))
             IN ('1', 'true', 't', 'yes')
            THEN true
        WHEN lower(trim(cast({column(base_columns, 'win')} AS VARCHAR)))
             IN ('0', 'false', 'f', 'no')
            THEN false
        ELSE NULL
    END AS win
    """,
    f"{number(base_columns, 'numMinutes')} AS minutes",
    f"{text(base_columns, 'startingPosition')} AS starting_position",
    f"{text(base_columns, 'comment')} AS comment",
]

base_select.extend(
    f"{number(base_columns, source_name)} AS {target_name}"
    for source_name, target_name in traditional_fields
)

base_output = [
    "b.player_id",
    "b.player_name",
    "b.game_id",
    "b.game_date",
    "b.game_datetime",
    """
    printf(
        '%04d-%02d',
        b.season_start,
        (b.season_start + 1) % 100
    ) AS season_year
    """,
    "b.season_type",
    "b.source_game_type",
    "b.game_label",
    "b.game_sub_label",
    "b.series_game_number",
    "b.team_id",
    "b.team_name",
    "b.opponent_id",
    "b.opponent",
    "b.home",
    "b.win",
    "b.minutes",
    "b.starting_position IS NOT NULL AS started",
    "b.starting_position",
    "b.comment",
]

base_output.extend(
    f"b.{target_name}"
    for _, target_name in traditional_fields
)

advanced_output = [
    f"a.{target_name}"
    for _, target_name in advanced_fields
]

advanced_output.extend(
    f"a.{target_name}"
    for _, target_name in advanced_integer_fields
)

db.execute(f"""
CREATE TABLE player_games AS
WITH parsed AS (
    SELECT
        {", ".join(base_select)}
    FROM base_source
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
            WHEN source_game_type IN (
                'NBA Emirates Cup',
                'Regular Season'
            )
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
    {", ".join(base_output)},
    {", ".join(advanced_output)}
FROM normalized AS b
LEFT JOIN advanced_games AS a
    ON a.player_id = b.player_id
   AND a.game_id = b.game_id
WHERE b.player_id IS NOT NULL
  AND b.game_id IS NOT NULL
  AND trim(b.game_id) <> ''
  AND b.game_datetime IS NOT NULL
  AND b.player_name <> ''
  AND b.minutes > 0
  AND b.minutes <= 80
  AND upper(coalesce(b.comment, '')) NOT LIKE 'DNP%'
  AND upper(coalesce(b.comment, '')) NOT LIKE 'DND%'
  AND upper(coalesce(b.comment, '')) NOT LIKE 'NWT%'
  AND b.pts IS NOT NULL
  AND b.reb IS NOT NULL
  AND b.ast IS NOT NULL
QUALIFY row_number() OVER (
    PARTITION BY b.player_id, b.game_id
    ORDER BY b.game_datetime, b.player_name
) = 1
""")

db.execute(f"""
CREATE TEMP VIEW player_source AS
SELECT *
FROM read_csv_auto(
    '{sql_path(players_source)}',
    header=true,
    all_varchar=true,
    sample_size=-1
)
""")

player_columns = {
    row[0]
    for row in db.execute("DESCRIBE player_source").fetchall()
}

db.execute(f"""
CREATE TABLE players AS
SELECT
    try_cast(
        {column(player_columns, 'personId')}
        AS BIGINT
    ) AS player_id,
    trim(concat_ws(
        ' ',
        {text(player_columns, 'firstName')},
        {text(player_columns, 'lastName')}
    )) AS player_name,
    try_cast(
        {column(player_columns, 'birthDate')}
        AS DATE
    ) AS birth_date,
    {text(player_columns, 'school')} AS school,
    {text(player_columns, 'country')} AS country,
    {number(player_columns, 'heightInches')} AS height_inches,
    {number(player_columns, 'bodyWeightLbs')} AS weight_lbs,
    try_cast(
        {column(player_columns, 'guard')}
        AS BOOLEAN
    ) AS guard,
    try_cast(
        {column(player_columns, 'forward')}
        AS BOOLEAN
    ) AS forward,
    try_cast(
        {column(player_columns, 'center')}
        AS BOOLEAN
    ) AS center,
    {text(player_columns, 'draftYear')} AS draft_year,
    {text(player_columns, 'draftRound')} AS draft_round,
    {text(player_columns, 'draftNumber')} AS draft_number,
    try_cast(
        {column(player_columns, 'fromYear')}
        AS INTEGER
    ) AS from_year,
    try_cast(
        {column(player_columns, 'toYear')}
        AS INTEGER
    ) AS to_year
FROM player_source
WHERE try_cast(
    {column(player_columns, 'personId')}
    AS BIGINT
) IS NOT NULL
QUALIFY row_number() OVER (
    PARTITION BY try_cast(
        {column(player_columns, 'personId')}
        AS BIGINT
    )
    ORDER BY try_cast(
        {column(player_columns, 'toYear')}
        AS INTEGER
    ) DESC NULLS LAST
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
CREATE INDEX players_idx
ON players(player_id)
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
        ('source', ?),
        ('extended_source', ?),
        ('players_source', ?)
    """,
    [
        datetime.now(timezone.utc).isoformat(),
        str(source),
        str(extended_source),
        str(players_source),
    ],
)

rows = db.execute(
    "SELECT count(*) FROM player_games"
).fetchone()[0]

players = db.execute(
    "SELECT count(DISTINCT player_id) FROM player_games"
).fetchone()[0]

games = db.execute(
    "SELECT count(DISTINCT game_id) FROM player_games"
).fetchone()[0]

coverage = db.execute("""
    SELECT
        min(game_date),
        max(game_date),
        count(DISTINCT season_year)
    FROM player_games
""").fetchone()

advanced_coverage = db.execute("""
    SELECT
        min(game_date) FILTER (
            WHERE possessions IS NOT NULL
        ),
        max(game_date) FILTER (
            WHERE possessions IS NOT NULL
        ),
        count(*) FILTER (
            WHERE possessions IS NOT NULL
        )
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
    raise SystemExit(
        f"The build produced {duplicates} duplicate player-game pairs."
    )

print(f"Built {target}")
print(f"{rows:,} player-games")
print(f"{players:,} players")
print(f"{games:,} games")
print(f"{coverage[2]} seasons")
print(f"{coverage[0]} to {coverage[1]}")
print(
    f"{advanced_coverage[2]:,} advanced rows "
    f"from {advanced_coverage[0]} to {advanced_coverage[1]}"
)

print("\nSeason types")

for row in db.execute("""
    SELECT season_type, count(*)
    FROM player_games
    GROUP BY season_type
    ORDER BY count(*) DESC
""").fetchall():
    print(row)

db.close()
