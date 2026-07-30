import gzip
import os
import shutil
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "data" / "app" / "context.duckdb"
TARGET = Path(os.environ.get("CONTEXT_DB_PATH", DEFAULT_TARGET))
URL = os.environ.get("CONTEXT_DB_URL")
TOKEN = os.environ.get("GITHUB_TOKEN")

if TARGET.exists() and TARGET.stat().st_size > 0:
    print(f"Database already exists at {TARGET}")
    raise SystemExit(0)

if not URL:
    raise SystemExit("CONTEXT_DB_URL is required when the database is absent.")

TARGET.parent.mkdir(parents=True, exist_ok=True)
DOWNLOAD = TARGET.with_suffix(TARGET.suffix + ".download")

headers = {
    "Accept": "application/octet-stream",
    "User-Agent": "NBAContext database downloader",
}

if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"
    headers["X-GitHub-Api-Version"] = "2022-11-28"

with httpx.stream(
    "GET",
    URL,
    headers=headers,
    follow_redirects=True,
    timeout=300.0,
) as response:
    response.raise_for_status()

    with DOWNLOAD.open("wb") as output:
        for chunk in response.iter_bytes(1024 * 1024):
            output.write(chunk)

try:
    with gzip.open(DOWNLOAD, "rb") as compressed:
        with TARGET.open("wb") as output:
            shutil.copyfileobj(compressed, output, length=1024 * 1024)
except (gzip.BadGzipFile, EOFError):
    DOWNLOAD.replace(TARGET)
else:
    DOWNLOAD.unlink()

if not TARGET.exists() or TARGET.stat().st_size == 0:
    raise SystemExit("Database download produced an empty file.")

print(f"Database ready at {TARGET} ({TARGET.stat().st_size:,} bytes)")
