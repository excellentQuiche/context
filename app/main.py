from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "app" / "context.duckdb"
STATIC_PATH = ROOT / "app" / "static"

app = FastAPI(title="Context")
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

METRICS = {
    "points": ("pts", "PPG"),
    "rebounds": ("reb", "RPG"),
    "assists": ("ast", "APG"),
    "points_per_36": (None, "PTS/36"),
}


def connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not built. Run scripts/build_database.py first.",
        )

    return duckdb.connect(str(DB_PATH), read_only=True)


def validate_metric(metric):
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail="Unsupported metric")


def rolling_query(metric, window):
    frame = window - 1

    if metric == "points_per_36":
        rolling_values = f"""
            sum(pts) OVER (
                PARTITION BY player_id, season_year, season_type
                ORDER BY game_number
                ROWS BETWEEN {frame} PRECEDING AND CURRENT ROW
            ) AS rolling_points,
            sum(minutes) OVER (
                PARTITION BY player_id, season_year, season_type
                ORDER BY game_number
                ROWS BETWEEN {frame} PRECEDING AND CURRENT ROW
            ) AS rolling_minutes
        """

        value = """
            CASE
                WHEN rolling_minutes > 0
                THEN rolling_points * 36.0 / rolling_minutes
            END
        """
    else:
        column = METRICS[metric][0]

        rolling_values = f"""
            sum({column}) OVER (
                PARTITION BY player_id, season_year, season_type
                ORDER BY game_number
                ROWS BETWEEN {frame} PRECEDING AND CURRENT ROW
            ) AS rolling_total
        """

        value = "rolling_total / sample_size"

    return f"""
        WITH ordered AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY player_id, season_year, season_type
                    ORDER BY game_date, game_id
                ) AS game_number
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
        ),
        rolling AS (
            SELECT
                *,
                count(*) OVER (
                    PARTITION BY player_id, season_year, season_type
                    ORDER BY game_number
                    ROWS BETWEEN {frame} PRECEDING AND CURRENT ROW
                ) AS sample_size,
                {rolling_values}
            FROM ordered
        ),
        scored AS (
            SELECT
                *,
                {value} AS rolling_value
            FROM rolling
        )
    """


@app.get("/")
def home():
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/api/meta")
def meta():
    with connection() as db:
        seasons = [
            row[0]
            for row in db.execute("""
                SELECT DISTINCT season_year
                FROM player_games
                WHERE season_type = 'Regular Season'
                ORDER BY season_year DESC
            """).fetchall()
        ]

        built_at = db.execute("""
            SELECT value
            FROM app_metadata
            WHERE key = 'built_at'
        """).fetchone()

    return {
        "seasons": seasons,
        "built_at": built_at[0] if built_at else None,
    }


@app.get("/api/players")
def players(season: str):
    with connection() as db:
        rows = db.execute(
            """
            SELECT DISTINCT
                player_id,
                player_name
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
            ORDER BY player_name
            """,
            [season],
        ).fetchall()

    return [
        {
            "id": player_id,
            "name": player_name,
        }
        for player_id, player_name in rows
    ]


@app.get("/api/result")
def result(
    season: str,
    player_id: int,
    metric: str = "points",
    window: int = Query(2, ge=2, le=20),
):
    validate_metric(metric)

    unit = METRICS[metric][1]
    query = rolling_query(metric, window)

    with connection() as db:
        best = db.execute(
            query
            + """
            SELECT
                player_name,
                rolling_value,
                game_number,
                game_date
            FROM scored
            WHERE player_id = ?
              AND sample_size = ?
            ORDER BY rolling_value DESC, game_date ASC
            LIMIT 1
            """,
            [season, player_id, window],
        ).fetchone()

        if not best:
            raise HTTPException(
                status_code=404,
                detail="No complete window found",
            )

        player_name, value, end_number, end_date = best

        games = db.execute(
            """
            SELECT
                game_id,
                game_date,
                opponent,
                minutes,
                pts,
                reb,
                ast
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
              AND player_id = ?
            ORDER BY game_date, game_id
            """,
            [season, player_id],
        ).fetchall()

    end = int(end_number)
    start = end - window
    selected_ids = {
        game[0]
        for game in games[start:end]
    }

    return {
        "player_id": player_id,
        "player_name": player_name,
        "season": season,
        "metric": metric,
        "unit": unit,
        "window": window,
        "value": round(value, 2),
        "end_date": str(end_date),
        "games": [
            {
                "game_id": game_id,
                "date": str(game_date),
                "opponent": opponent,
                "minutes": minutes,
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "selected": game_id in selected_ids,
            }
            for game_id, game_date, opponent, minutes, pts, reb, ast in games
        ],
    }


@app.get("/api/similar")
def similar(
    season: str,
    metric: str = "points",
    window: int = Query(2, ge=2, le=20),
    limit: int = Query(20, ge=1, le=100),
):
    validate_metric(metric)

    unit = METRICS[metric][1]
    query = rolling_query(metric, window)

    with connection() as db:
        rows = db.execute(
            query
            + """
            , ranked AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY player_id
                        ORDER BY rolling_value DESC, game_date ASC
                    ) AS player_rank
                FROM scored
                WHERE sample_size = ?
            )
            SELECT
                player_id,
                player_name,
                rolling_value,
                game_date
            FROM ranked
            WHERE player_rank = 1
            ORDER BY rolling_value DESC
            LIMIT ?
            """,
            [season, window, limit],
        ).fetchall()

    return {
        "unit": unit,
        "results": [
            {
                "rank": index,
                "player_id": player_id,
                "player_name": player_name,
                "value": round(value, 2),
                "end_date": str(end_date),
            }
            for index, (
                player_id,
                player_name,
                value,
                end_date,
            ) in enumerate(rows, start=1)
        ],
    }
