import duckdb
import pytest
from fastapi.testclient import TestClient

from app.main import DB_PATH, app

client = TestClient(app)


def find_player(minimum_games=5, advanced=False):
    advanced_filter = (
        "AND possessions IS NOT NULL"
        if advanced
        else ""
    )

    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        row = db.execute(
            f"""
            SELECT
                season_year,
                player_id,
                count(*) AS games
            FROM player_games
            WHERE season_type = 'Regular Season'
              {advanced_filter}
            GROUP BY season_year, player_id
            HAVING count(*) >= ?
            ORDER BY season_year DESC, games DESC, player_id
            LIMIT 1
            """,
            [minimum_games],
        ).fetchone()

    return row


def test_seasons():
    response = client.get("/api/meta")

    assert response.status_code == 200

    seasons = response.json()["seasons"]

    assert seasons
    assert seasons == sorted(seasons, reverse=True)
    assert seasons[-1] == "1951-52"


def test_metric_catalog():
    response = client.get("/api/metrics")

    assert response.status_code == 200

    metrics = response.json()["metrics"]
    metric_ids = {metric["id"] for metric in metrics}

    assert len(metrics) >= 80
    assert "pts" in metric_ids
    assert "true_shooting_percentage" in metric_ids
    assert "player_impact_estimate" in metric_ids
    assert "percent_team_points" in metric_ids


def test_players():
    season, _, _ = find_player()

    response = client.get(
        "/api/players",
        params={"season": season},
    )

    assert response.status_code == 200

    players = response.json()
    names = [player["name"] for player in players]

    assert players
    assert names == sorted(names)


def test_points_window():
    season, player_id, _ = find_player()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "points",
            "window": 5,
        },
    )

    assert response.status_code == 200

    result = response.json()
    selected = [game for game in result["games"] if game["selected"]]
    expected = sum(game["pts"] for game in selected) / len(selected)

    assert len(selected) == 5
    assert result["value"] == pytest.approx(expected, abs=0.01)


def test_points_per_36_window():
    season, player_id, _ = find_player()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "points_per_36",
            "window": 5,
        },
    )

    assert response.status_code == 200

    result = response.json()
    selected = [game for game in result["games"] if game["selected"]]
    points = sum(game["pts"] for game in selected)
    minutes = sum(game["minutes"] for game in selected)
    expected = points * 36 / minutes

    assert len(selected) == 5
    assert result["value"] == pytest.approx(expected, abs=0.01)


def test_season_total_points():
    season, player_id, _ = find_player()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "pts",
            "calculation": "total",
            "scope": "season",
        },
    )

    assert response.status_code == 200

    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        expected = db.execute(
            """
            SELECT sum(pts)
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
              AND player_id = ?
            """,
            [season, player_id],
        ).fetchone()[0]

    assert response.json()["value"] == pytest.approx(expected, abs=0.01)


def test_weighted_field_goal_percentage():
    season, player_id, _ = find_player()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "field_goal_percentage",
            "calculation": "weighted",
            "scope": "season",
        },
    )

    assert response.status_code == 200

    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        made, attempted = db.execute(
            """
            SELECT sum(fgm), sum(fga)
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
              AND player_id = ?
            """,
            [season, player_id],
        ).fetchone()

    expected = made / attempted * 100

    assert response.json()["value"] == pytest.approx(expected, abs=0.01)


def test_per_100_points():
    season, player_id, _ = find_player(advanced=True)

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "pts",
            "calculation": "per_100",
            "scope": "season",
        },
    )

    assert response.status_code == 200

    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        points, possessions = db.execute(
            """
            SELECT sum(pts), sum(possessions)
            FROM player_games
            WHERE season_year = ?
              AND season_type = 'Regular Season'
              AND player_id = ?
            """,
            [season, player_id],
        ).fetchone()

    expected = points * 100 / possessions

    assert response.json()["value"] == pytest.approx(expected, abs=0.01)


def test_advanced_metric_unavailable_before_1996():
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        player_id = db.execute(
            """
            SELECT player_id
            FROM player_games
            WHERE season_year = '1951-52'
              AND season_type = 'Regular Season'
            LIMIT 1
            """
        ).fetchone()[0]

    response = client.get(
        "/api/result",
        params={
            "season": "1951-52",
            "player_id": player_id,
            "metric": "usage_percentage",
            "scope": "season",
        },
    )

    assert response.status_code == 404


def test_leaderboard_order():
    season, _, _ = find_player()

    response = client.get(
        "/api/similar",
        params={
            "season": season,
            "metric": "points",
            "window": 5,
            "limit": 20,
        },
    )

    assert response.status_code == 200

    results = response.json()["results"]
    values = [row["value"] for row in results]
    player_ids = [row["player_id"] for row in results]
    ranks = [row["rank"] for row in results]

    assert results
    assert values == sorted(values, reverse=True)
    assert len(player_ids) == len(set(player_ids))
    assert ranks == list(range(1, len(results) + 1))


def test_low_leaderboard_order():
    season, _, _ = find_player(advanced=True)

    response = client.get(
        "/api/similar",
        params={
            "season": season,
            "metric": "defensive_rating",
            "scope": "season",
            "direction": "low",
            "limit": 20,
        },
    )

    assert response.status_code == 200

    values = [
        row["value"]
        for row in response.json()["results"]
    ]

    assert values == sorted(values)


def test_incomplete_window():
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        season, player_id, games = db.execute(
            """
            SELECT
                season_year,
                player_id,
                count(*) AS games
            FROM player_games
            WHERE season_type = 'Regular Season'
            GROUP BY season_year, player_id
            HAVING count(*) BETWEEN 1 AND 19
            ORDER BY games, season_year, player_id
            LIMIT 1
            """
        ).fetchone()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "points",
            "window": games + 1,
        },
    )

    assert response.status_code == 404


def test_invalid_metric():
    season, player_id, _ = find_player()

    response = client.get(
        "/api/result",
        params={
            "season": season,
            "player_id": player_id,
            "metric": "made_up_stat",
            "window": 5,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported metric"
