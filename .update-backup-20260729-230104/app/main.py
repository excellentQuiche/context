import html
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import duckdb
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.metrics import CALCULATIONS, LEGACY_METRICS, METRICS, SCOPES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app" / "context.duckdb"
DB_PATH = Path(os.environ.get("CONTEXT_DB_PATH", DEFAULT_DB_PATH))
STATIC_PATH = ROOT / "app" / "static"
WIKIMEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "NBAContext/1.0 educational basketball statistics project"

app = FastAPI(title="NBAContext")
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


def connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not available. Build it locally or configure CONTEXT_DB_PATH.",
        )

    return duckdb.connect(str(DB_PATH), read_only=True)


def resolve_metric(metric, calculation):
    requested_metric = metric

    if metric in LEGACY_METRICS:
        metric, legacy_calculation = LEGACY_METRICS[metric]

        if calculation is None:
            calculation = legacy_calculation

    if metric not in METRICS:
        raise HTTPException(status_code=400, detail="Unsupported metric")

    spec = METRICS[metric]
    calculation = calculation or spec["default_calculation"]

    if calculation not in spec["calculations"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported calculation for this metric",
        )

    return requested_metric, metric, spec, calculation


def resolve_scope(scope):
    if scope not in SCOPES:
        raise HTTPException(status_code=400, detail="Unsupported scope")

    return scope


def resolve_direction(spec, direction):
    direction = direction or spec["default_direction"]

    if direction not in {"high", "low"}:
        raise HTTPException(status_code=400, detail="Unsupported direction")

    return direction


def metric_unit(spec, calculation):
    unit = spec["unit"]

    if calculation == "per_game":
        return spec.get("per_game_unit") or f"{unit}/G"

    if calculation == "per_36":
        return f"{unit}/36"

    if calculation == "per_100":
        return f"{unit}/100"

    return unit


def aggregate_plan(spec, calculation, over=None, window=None):
    suffix = f" {over}" if over else ""

    def aggregate(function, expression):
        return f"{function}({expression}){suffix}"

    kind = spec["kind"]
    scale = spec["scale"]
    selections = [f"{aggregate('count', '*')} AS games_in_scope"]

    if kind == "count":
        expression = spec["expression"]
        selections.extend(
            [
                f"{aggregate('count', expression)} AS observations",
                f"{aggregate('sum', expression)} AS metric_sum",
            ]
        )

        if calculation == "per_game":
            value = "metric_sum / observations"
            valid = "observations > 0"
        elif calculation == "total":
            value = "metric_sum"
            valid = "observations > 0"
        elif calculation == "per_36":
            weight = f"CASE WHEN ({expression}) IS NOT NULL THEN minutes END"
            selections.append(f"{aggregate('sum', weight)} AS weight_sum")
            value = "metric_sum * 36.0 / weight_sum"
            valid = "observations > 0 AND weight_sum > 0"
        else:
            weight = (
                f"CASE WHEN ({expression}) IS NOT NULL "
                "THEN possessions END"
            )
            selections.append(f"{aggregate('sum', weight)} AS weight_sum")
            value = "metric_sum * 100.0 / weight_sum"
            valid = "observations > 0 AND weight_sum > 0"

    elif kind == "ratio":
        if calculation == "weighted":
            numerator = spec["numerator"]
            denominator = spec["denominator"]
            available = (
                f"({numerator}) IS NOT NULL "
                f"AND ({denominator}) IS NOT NULL"
            )

            selections.extend(
                [
                    f"{aggregate('count', f'CASE WHEN {available} THEN 1 END')} AS observations",
                    f"{aggregate('sum', f'CASE WHEN {available} THEN ({numerator}) END')} AS numerator_sum",
                    f"{aggregate('sum', f'CASE WHEN {available} THEN ({denominator}) END')} AS denominator_sum",
                ]
            )

            value = f"numerator_sum / denominator_sum * {scale}"
            valid = "observations > 0 AND denominator_sum > 0"
        else:
            expression = spec["column"]
            selections.extend(
                [
                    f"{aggregate('count', expression)} AS observations",
                    f"{aggregate('avg', expression)} AS metric_average",
                ]
            )
            value = f"metric_average * {scale}"
            valid = "observations > 0"

    else:
        expression = spec["expression"]
        selections.append(f"{aggregate('count', expression)} AS observations")

        if calculation == "game_average":
            selections.append(
                f"{aggregate('avg', expression)} AS metric_average"
            )
            value = f"metric_average * {scale}"
            valid = "observations > 0"
        elif calculation == "minute_weighted":
            weighted = (
                f"CASE WHEN ({expression}) IS NOT NULL "
                f"THEN ({expression}) * minutes END"
            )
            weight = (
                f"CASE WHEN ({expression}) IS NOT NULL "
                "THEN minutes END"
            )
            selections.extend(
                [
                    f"{aggregate('sum', weighted)} AS weighted_sum",
                    f"{aggregate('sum', weight)} AS weight_sum",
                ]
            )
            value = f"weighted_sum / weight_sum * {scale}"
            valid = "observations > 0 AND weight_sum > 0"
        else:
            weighted = (
                f"CASE WHEN ({expression}) IS NOT NULL "
                f"THEN ({expression}) * possessions END"
            )
            weight = (
                f"CASE WHEN ({expression}) IS NOT NULL "
                "THEN possessions END"
            )
            selections.extend(
                [
                    f"{aggregate('sum', weighted)} AS weighted_sum",
                    f"{aggregate('sum', weight)} AS weight_sum",
                ]
            )
            value = f"weighted_sum / weight_sum * {scale}"
            valid = "observations > 0 AND weight_sum > 0"

    if window is not None:
        valid = (
            f"games_in_scope = {window} "
            f"AND observations = {window} "
            f"AND {valid}"
        )

    return selections, value, valid


def metric_query(spec, calculation, scope, window):
    if scope == "window":
        frame = (
            "OVER ("
            "PARTITION BY player_id, season_year, season_type "
            "ORDER BY game_number "
            f"ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW"
            ")"
        )
        selections, value, valid = aggregate_plan(
            spec,
            calculation,
            over=frame,
            window=window,
        )

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
            aggregated AS (
                SELECT
                    *,
                    {", ".join(selections)}
                FROM ordered
            ),
            scored AS (
                SELECT
                    *,
                    {value} AS metric_value
                FROM aggregated
                WHERE {valid}
            )
        """

    selections, value, valid = aggregate_plan(spec, calculation)

    return f"""
        WITH filtered AS (
            SELECT *
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
        ),
        aggregated AS (
            SELECT
                player_id,
                max(player_name) AS player_name,
                min(game_date) AS start_date,
                max(game_date) AS end_date,
                {", ".join(selections)}
            FROM filtered
            GROUP BY player_id
        ),
        scored AS (
            SELECT
                *,
                {value} AS metric_value
            FROM aggregated
            WHERE {valid}
        )
    """


def chart_expression(spec, calculation):
    kind = spec["kind"]
    scale = spec["scale"]

    if kind == "count":
        expression = spec["expression"]

        if calculation == "per_36":
            return (
                f"CASE WHEN minutes > 0 "
                f"THEN ({expression}) * 36.0 / minutes END"
            )

        if calculation == "per_100":
            return (
                f"CASE WHEN possessions > 0 "
                f"THEN ({expression}) * 100.0 / possessions END"
            )

        return expression

    if kind == "ratio":
        if calculation == "weighted":
            numerator = spec["numerator"]
            denominator = spec["denominator"]
            return (
                f"CASE WHEN ({denominator}) > 0 "
                f"THEN ({numerator}) / ({denominator}) * {scale} END"
            )

        return f"{spec['column']} * {scale}"

    return f"({spec['expression']}) * {scale}"


def get_player_name(db, player_id):
    row = db.execute(
        """
        SELECT player_name
        FROM players
        WHERE player_id = ?
          AND player_name IS NOT NULL
          AND trim(player_name) <> ''
        LIMIT 1
        """,
        [player_id],
    ).fetchone()

    if row:
        return row[0]

    row = db.execute(
        """
        SELECT player_name
        FROM player_games
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT 1
        """,
        [player_id],
    ).fetchone()

    return row[0] if row else None


def get_player_team(db, season, player_id):
    row = db.execute(
        """
        SELECT
            team_id,
            team_name,
            count(*) AS games,
            max(game_date) AS latest_game
        FROM player_games
        WHERE season_year = ?
          AND season_type = 'Regular Season'
          AND player_id = ?
        GROUP BY team_id, team_name
        ORDER BY games DESC, latest_game DESC
        LIMIT 1
        """,
        [season, player_id],
    ).fetchone()

    if not row:
        return None, None

    return row[0], row[1]


def get_season_game_count(db, season, player_id):
    return db.execute(
        """
        SELECT count(*)
        FROM player_games
        WHERE season_year = ?
          AND season_type = 'Regular Season'
          AND player_id = ?
        """,
        [season, player_id],
    ).fetchone()[0]


def get_player_summary(
    db,
    season,
    player_id,
    spec,
    calculation,
    scope,
    window,
    direction,
):
    player_name = get_player_name(db, player_id)

    if player_name is None:
        raise HTTPException(status_code=404, detail="Player not found")

    team_id, team_name = get_player_team(db, season, player_id)
    games_count = get_season_game_count(db, season, player_id)
    query = metric_query(spec, calculation, scope, window)
    order = "DESC" if direction == "high" else "ASC"

    if scope == "window":
        row = db.execute(
            query
            + f"""
            SELECT
                metric_value,
                game_number,
                game_date,
                games_in_scope,
                observations
            FROM scored
            WHERE player_id = ?
            ORDER BY metric_value {order}, game_date ASC
            LIMIT 1
            """,
            [season, player_id],
        ).fetchone()

        if row:
            value, game_number, end_date, scope_games, observations = row
            return {
                "season": season,
                "player_id": player_id,
                "player_name": player_name,
                "team_id": team_id,
                "team_name": team_name,
                "status": "played",
                "value": round(value, 2),
                "games_count": games_count,
                "scope_games": scope_games,
                "observations": observations,
                "start_date": None,
                "end_date": str(end_date),
                "end_game_number": int(game_number),
            }

    else:
        row = db.execute(
            query
            + """
            SELECT
                metric_value,
                start_date,
                end_date,
                games_in_scope,
                observations
            FROM scored
            WHERE player_id = ?
            """,
            [season, player_id],
        ).fetchone()

        if row:
            value, start_date, end_date, scope_games, observations = row
            return {
                "season": season,
                "player_id": player_id,
                "player_name": player_name,
                "team_id": team_id,
                "team_name": team_name,
                "status": "played",
                "value": round(value, 2),
                "games_count": games_count,
                "scope_games": scope_games,
                "observations": observations,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "end_game_number": None,
            }

    if games_count == 0:
        return {
            "season": season,
            "player_id": player_id,
            "player_name": player_name,
            "team_id": None,
            "team_name": None,
            "status": "did_not_play",
            "value": 0.0 if calculation == "total" else None,
            "games_count": 0,
            "scope_games": 0,
            "observations": 0,
            "start_date": None,
            "end_date": None,
            "end_game_number": None,
        }

    return {
        "season": season,
        "player_id": player_id,
        "player_name": player_name,
        "team_id": team_id,
        "team_name": team_name,
        "status": "no_qualifying_result",
        "value": None,
        "games_count": games_count,
        "scope_games": 0,
        "observations": 0,
        "start_date": None,
        "end_date": None,
        "end_game_number": None,
    }


def strip_markup(value):
    value = re.sub(r"<[^>]+>", "", value or "")
    return " ".join(html.unescape(value).split())


def metadata_value(metadata, key):
    value = metadata.get(key, {})
    return value.get("value", "") if isinstance(value, dict) else ""


def reusable_license(name):
    normalized = name.lower()
    return (
        normalized.startswith("cc ")
        or normalized.startswith("cc-")
        or "creative commons" in normalized
        or "public domain" in normalized
    )


@lru_cache(maxsize=2048)
def find_commons_portrait(player_name):
    headers = {"User-Agent": USER_AGENT}
    search_params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f'"{player_name}" basketball player',
        "gsrnamespace": 0,
        "gsrlimit": 5,
        "prop": "pageimages|pageterms",
        "piprop": "name",
        "wbptterms": "description",
        "redirects": 1,
    }

    try:
        with httpx.Client(
            headers=headers,
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            search_response = client.get(WIKIMEDIA_API, params=search_params)
            search_response.raise_for_status()
            pages = search_response.json().get("query", {}).get("pages", {})

            candidates = []

            for page in pages.values():
                image_name = page.get("pageimage")

                if not image_name:
                    continue

                title = page.get("title", "")
                descriptions = page.get("terms", {}).get("description", [])
                description = " ".join(descriptions).lower()
                exact = title.casefold() == player_name.casefold()
                basketball = "basketball" in description
                candidates.append((exact, basketball, image_name, title))

            candidates.sort(reverse=True)

            for _, _, image_name, title in candidates:
                file_title = image_name

                if not file_title.lower().startswith("file:"):
                    file_title = f"File:{file_title}"

                commons_params = {
                    "action": "query",
                    "format": "json",
                    "titles": file_title,
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "iiurlwidth": 520,
                }
                commons_response = client.get(
                    COMMONS_API,
                    params=commons_params,
                )
                commons_response.raise_for_status()
                commons_pages = (
                    commons_response.json().get("query", {}).get("pages", {})
                )

                for commons_page in commons_pages.values():
                    image_info = commons_page.get("imageinfo", [])

                    if not image_info:
                        continue

                    image = image_info[0]
                    metadata = image.get("extmetadata", {})
                    license_name = strip_markup(
                        metadata_value(metadata, "LicenseShortName")
                    )

                    if not reusable_license(license_name):
                        continue

                    artist = strip_markup(metadata_value(metadata, "Artist"))
                    credit = artist or "Wikimedia Commons contributor"
                    source_url = (
                        "https://commons.wikimedia.org/wiki/"
                        + quote(file_title.replace(" ", "_"), safe=":()_-")
                    )

                    return {
                        "url": image.get("thumburl") or image.get("url"),
                        "source_url": source_url,
                        "credit": credit,
                        "license": license_name,
                        "article": title,
                    }
    except (httpx.HTTPError, ValueError, KeyError):
        return None

    return None


@app.get("/")
def home():
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/api/health")
def health():
    with connection() as db:
        db.execute("SELECT 1").fetchone()

    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    with connection() as db:
        seasons = [
            row[0]
            for row in db.execute(
                """
                SELECT DISTINCT season_year
                FROM player_games
                WHERE season_type = 'Regular Season'
                ORDER BY season_year DESC
                """
            ).fetchall()
        ]

        built_at = db.execute(
            """
            SELECT value
            FROM app_metadata
            WHERE key = 'built_at'
            """
        ).fetchone()

    return {
        "seasons": seasons,
        "built_at": built_at[0] if built_at else None,
    }


@app.get("/api/metrics")
def metrics():
    results = []

    for metric_id, spec in METRICS.items():
        results.append(
            {
                "id": metric_id,
                "label": spec["label"],
                "category": spec["category"],
                "calculations": spec["calculations"],
                "default_calculation": spec["default_calculation"],
                "default_direction": spec["default_direction"],
                "unit": spec["unit"],
            }
        )

    scopes = dict(SCOPES)
    scopes["window"] = "Best streak"

    return {
        "metrics": results,
        "calculations": CALCULATIONS,
        "scopes": scopes,
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
        {"id": player_id, "name": player_name}
        for player_id, player_name in rows
    ]


@app.get("/api/all-players")
def all_players():
    with connection() as db:
        rows = db.execute(
            """
            WITH combined AS (
                SELECT
                    player_id,
                    player_name,
                    from_year,
                    to_year,
                    0 AS source_order
                FROM players
                WHERE player_id IS NOT NULL

                UNION ALL

                SELECT
                    player_id,
                    max(player_name) AS player_name,
                    cast(min(extract(year FROM game_date)) AS INTEGER),
                    cast(max(extract(year FROM game_date)) AS INTEGER),
                    1 AS source_order
                FROM player_games
                GROUP BY player_id
            ),
            grouped AS (
                SELECT
                    player_id,
                    coalesce(
                        max(player_name) FILTER (WHERE source_order = 0),
                        max(player_name)
                    ) AS player_name,
                    coalesce(
                        min(from_year) FILTER (WHERE source_order = 0),
                        min(from_year)
                    ) AS from_year,
                    coalesce(
                        max(to_year) FILTER (WHERE source_order = 0),
                        max(to_year)
                    ) AS to_year
                FROM combined
                GROUP BY player_id
            )
            SELECT
                player_id,
                player_name,
                from_year,
                to_year
            FROM grouped
            WHERE player_name IS NOT NULL
              AND trim(player_name) <> ''
            ORDER BY player_name, player_id
            """
        ).fetchall()

    return [
        {
            "id": player_id,
            "name": player_name,
            "from_year": from_year,
            "to_year": to_year,
        }
        for player_id, player_name, from_year, to_year in rows
    ]


@app.get("/api/player-image")
def player_image(player_id: int, season: str):
    with connection() as db:
        player_name = get_player_name(db, player_id)
        _, team_name = get_player_team(db, season, player_id)

    if player_name is None:
        raise HTTPException(status_code=404, detail="Player not found")

    image = find_commons_portrait(player_name)

    return {
        "player_id": player_id,
        "player_name": player_name,
        "season": season,
        "team_name": team_name,
        "image": image,
    }


@app.get("/api/result")
def result(
    season: str,
    player_id: int,
    metric: str = "points",
    calculation: str | None = None,
    scope: str = "window",
    direction: str | None = None,
    window: int = Query(2, ge=2, le=20),
):
    requested_metric, metric_id, spec, calculation = resolve_metric(
        metric,
        calculation,
    )
    scope = resolve_scope(scope)
    direction = resolve_direction(spec, direction)
    order = "DESC" if direction == "high" else "ASC"
    query = metric_query(spec, calculation, scope, window)

    with connection() as db:
        if scope == "window":
            best = db.execute(
                query
                + f"""
                SELECT
                    player_name,
                    metric_value,
                    game_number,
                    game_date,
                    games_in_scope,
                    observations
                FROM scored
                WHERE player_id = ?
                ORDER BY metric_value {order}, game_date ASC
                LIMIT 1
                """,
                [season, player_id],
            ).fetchone()
        else:
            best = db.execute(
                query
                + """
                SELECT
                    player_name,
                    metric_value,
                    start_date,
                    end_date,
                    games_in_scope,
                    observations
                FROM scored
                WHERE player_id = ?
                """,
                [season, player_id],
            ).fetchone()

        if not best:
            raise HTTPException(
                status_code=404,
                detail="No qualifying result found",
            )

        team_id, team_name = get_player_team(db, season, player_id)
        chart_value = chart_expression(spec, calculation)
        games = db.execute(
            f"""
            SELECT
                game_id,
                game_date,
                opponent,
                minutes,
                pts,
                reb,
                ast,
                {chart_value} AS chart_value
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
              AND player_id = ?
            ORDER BY game_date, game_id
            """,
            [season, player_id],
        ).fetchall()

    if scope == "window":
        (
            player_name,
            value,
            end_number,
            end_date,
            games_count,
            observations,
        ) = best
        end = int(end_number)
        start = end - window
        selected_ids = {game[0] for game in games[start:end]}
        start_date = games[start][1]
    else:
        (
            player_name,
            value,
            start_date,
            end_date,
            games_count,
            observations,
        ) = best
        selected_ids = {game[0] for game in games}

    return {
        "player_id": player_id,
        "player_name": player_name,
        "team_id": team_id,
        "team_name": team_name,
        "season": season,
        "metric": requested_metric,
        "resolved_metric": metric_id,
        "metric_label": spec["label"],
        "calculation": calculation,
        "scope": scope,
        "direction": direction,
        "unit": metric_unit(spec, calculation),
        "window": window,
        "value": round(value, 2),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "games_count": games_count,
        "observations": observations,
        "games": [
            {
                "game_id": game_id,
                "date": str(game_date),
                "opponent": opponent,
                "minutes": minutes,
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "chart_value": game_chart_value,
                "selected": game_id in selected_ids,
            }
            for (
                game_id,
                game_date,
                opponent,
                minutes,
                pts,
                reb,
                ast,
                game_chart_value,
            ) in games
        ],
    }


@app.get("/api/compare")
def compare(
    primary_player_id: int,
    comparison_player_id: int,
    primary_season: str | None = None,
    comparison_season: str | None = None,
    season: str | None = None,
    metric: str = "points",
    calculation: str | None = None,
    scope: str = "window",
    direction: str | None = None,
    window: int = Query(2, ge=2, le=20),
):
    primary_season = primary_season or season
    comparison_season = comparison_season or season or primary_season

    if not primary_season or not comparison_season:
        raise HTTPException(status_code=422, detail="Both seasons are required")

    _, metric_id, spec, calculation = resolve_metric(metric, calculation)
    scope = resolve_scope(scope)
    direction = resolve_direction(spec, direction)

    with connection() as db:
        primary = get_player_summary(
            db,
            primary_season,
            primary_player_id,
            spec,
            calculation,
            scope,
            window,
            direction,
        )
        comparison = get_player_summary(
            db,
            comparison_season,
            comparison_player_id,
            spec,
            calculation,
            scope,
            window,
            direction,
        )

    difference = None

    if primary["value"] is not None and comparison["value"] is not None:
        difference = round(primary["value"] - comparison["value"], 2)

    return {
        "primary_season": primary_season,
        "comparison_season": comparison_season,
        "metric": metric_id,
        "metric_label": spec["label"],
        "calculation": calculation,
        "scope": scope,
        "direction": direction,
        "unit": metric_unit(spec, calculation),
        "window": window,
        "primary": primary,
        "comparison": comparison,
        "difference": difference,
    }


@app.get("/api/similar")
def similar(
    season: str,
    metric: str = "points",
    calculation: str | None = None,
    scope: str = "window",
    direction: str | None = None,
    window: int = Query(2, ge=2, le=20),
    limit: int = Query(20, ge=1, le=100),
):
    _, metric_id, spec, calculation = resolve_metric(metric, calculation)
    scope = resolve_scope(scope)
    direction = resolve_direction(spec, direction)
    order = "DESC" if direction == "high" else "ASC"
    query = metric_query(spec, calculation, scope, window)

    with connection() as db:
        if scope == "window":
            rows = db.execute(
                query
                + f"""
                , ranked AS (
                    SELECT
                        *,
                        row_number() OVER (
                            PARTITION BY player_id
                            ORDER BY metric_value {order}, game_date ASC
                        ) AS player_rank
                    FROM scored
                )
                SELECT
                    player_id,
                    player_name,
                    metric_value,
                    game_date,
                    games_in_scope,
                    observations
                FROM ranked
                WHERE player_rank = 1
                ORDER BY metric_value {order}
                LIMIT ?
                """,
                [season, limit],
            ).fetchall()
        else:
            rows = db.execute(
                query
                + f"""
                SELECT
                    player_id,
                    player_name,
                    metric_value,
                    end_date,
                    games_in_scope,
                    observations
                FROM scored
                ORDER BY metric_value {order}
                LIMIT ?
                """,
                [season, limit],
            ).fetchall()

    return {
        "season": season,
        "metric": metric_id,
        "metric_label": spec["label"],
        "calculation": calculation,
        "scope": scope,
        "direction": direction,
        "unit": metric_unit(spec, calculation),
        "results": [
            {
                "rank": rank,
                "player_id": player_id,
                "player_name": player_name,
                "value": round(value, 2),
                "end_date": str(end_date),
                "games_count": games_count,
                "observations": observations,
            }
            for rank, (
                player_id,
                player_name,
                value,
                end_date,
                games_count,
                observations,
            ) in enumerate(rows, start=1)
        ],
    }
