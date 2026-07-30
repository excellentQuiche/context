import duckdb
from fastapi.testclient import TestClient

from app.main import DB_PATH, app

client = TestClient(app)


def find_cross_season_player():
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        return db.execute(
            """
            WITH seasons AS (
                SELECT
                    player_id,
                    season_year,
                    count(*) AS games
                FROM player_games
                WHERE season_type = 'Regular Season'
                GROUP BY player_id, season_year
                HAVING count(*) >= 5
            )
            SELECT
                first_season.season_year,
                second_season.season_year,
                first_season.player_id
            FROM seasons AS first_season
            JOIN seasons AS second_season
              ON second_season.player_id = first_season.player_id
             AND second_season.season_year > first_season.season_year
            ORDER BY second_season.season_year DESC,
                     first_season.season_year,
                     first_season.player_id
            LIMIT 1
            """
        ).fetchone()


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scope_label_uses_streak():
    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert response.json()["scopes"]["window"] == "Best streak"


def test_cross_season_comparison():
    first_season, second_season, player_id = find_cross_season_player()

    response = client.get(
        "/api/compare",
        params={
            "primary_season": first_season,
            "primary_player_id": player_id,
            "comparison_season": second_season,
            "comparison_player_id": player_id,
            "metric": "pts",
            "calculation": "per_game",
            "scope": "season",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["primary_season"] == first_season
    assert result["comparison_season"] == second_season
    assert result["primary"]["status"] == "played"
    assert result["comparison"]["status"] == "played"
    assert result["primary"]["season"] == first_season
    assert result["comparison"]["season"] == second_season


def test_revised_dashboard_structure():
    root = DB_PATH.parents[2]
    html = (root / "app" / "static" / "index.html").read_text()
    javascript = (root / "app" / "static" / "app.js").read_text()
    stylesheet = (root / "app" / "static" / "style.css").read_text()

    assert "What's in (or not in) a bar chart?" in html
    assert "How does this affect LeBron's legacy?" in html
    assert 'id="primary-chart"' in html
    assert 'id="comparison-chart"' in html
    assert 'id="primary-show-values"' in html
    assert 'id="comparison-show-values"' in html
    assert 'aria-disabled="true"' in html
    assert "LEAGUE LEADERS" in javascript
    assert "window.print" not in javascript
    assert "1880px" in stylesheet
