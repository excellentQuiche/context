import gzip
import os
import shutil
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "app" / "context.duckdb"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        request,
        file_pointer,
        code,
        message,
        headers,
        new_url,
    ):
        return None


def download_release_asset(url, token, destination):
    request = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "User-Agent": "NBAContext-Render-Build",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )

    opener = build_opener(NoRedirect)
    response = None

    try:
        response = opener.open(request, timeout=300)
    except HTTPError as error:
        if error.code not in {301, 302, 303, 307, 308}:
            raise

        location = error.headers.get("Location")

        if not location:
            raise RuntimeError(
                "GitHub redirected without providing a download URL."
            ) from error

        response = urlopen(
            Request(
                location,
                headers={
                    "User-Agent": "NBAContext-Render-Build",
                },
            ),
            timeout=300,
        )

    with response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def validate_database(path):
    db = duckdb.connect(str(path), read_only=True)

    try:
        player_games = db.execute(
            "SELECT count(*) FROM player_games"
        ).fetchone()[0]

        seasons = db.execute(
            "SELECT count(DISTINCT season_year) FROM player_games"
        ).fetchone()[0]
    finally:
        db.close()

    if player_games < 1_000_000:
        raise RuntimeError(
            f"Database validation failed: {player_games:,} player-games."
        )

    if seasons < 70:
        raise RuntimeError(
            f"Database validation failed: {seasons} seasons."
        )

    return player_games, seasons


def main():
    url = os.environ.get("CONTEXT_DB_URL", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not url:
        raise SystemExit("CONTEXT_DB_URL is not set.")

    if not token:
        raise SystemExit("GITHUB_TOKEN is not set.")

    TARGET.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=TARGET.parent
    ) as temporary_directory:
        temporary = Path(temporary_directory)
        compressed = temporary / "context.duckdb.gz"
        extracted = temporary / "context.duckdb"

        print("Downloading NBAContext database...")
        download_release_asset(url, token, compressed)

        print("Extracting NBAContext database...")
        with gzip.open(compressed, "rb") as source:
            with extracted.open("wb") as destination:
                shutil.copyfileobj(source, destination)

        player_games, seasons = validate_database(extracted)

        os.replace(extracted, TARGET)

    print(f"Database ready: {TARGET}")
    print(f"{player_games:,} player-games")
    print(f"{seasons} seasons")


if __name__ == "__main__":
    main()
