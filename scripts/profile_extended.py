import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "data" / "source" / "PlayerStatistics.csv"
EXTENDED_PATH = ROOT / "data" / "source" / "PlayerStatisticsExtended.csv"
PLAYERS_PATH = ROOT / "data" / "source" / "Players.csv"


def header(path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        columns = next(reader)
        sample = next(reader)

    return columns, dict(zip(columns, sample))


base_columns, _ = header(BASE_PATH)
extended_columns, extended_sample = header(EXTENDED_PATH)

base = set(base_columns)
extended = set(extended_columns)

print(f"Base size: {BASE_PATH.stat().st_size:,} bytes")
print(f"Extended size: {EXTENDED_PATH.stat().st_size:,} bytes")
print(f"Base columns: {len(base_columns)}")
print(f"Extended columns: {len(extended_columns)}")
print(f"Shared columns: {len(base & extended)}")
print(f"Extended-only columns: {len(extended - base)}")

print("\nExtended-only columns")

for name in extended_columns:
    if name not in base:
        print(name)

print("\nExtended-only sample values")

for name in extended_columns:
    if name not in base:
        print(f"{name}: {extended_sample.get(name)!r}")

if PLAYERS_PATH.exists():
    player_columns, _ = header(PLAYERS_PATH)

    print(f"\nPlayers.csv columns: {len(player_columns)}")

    for name in player_columns:
        print(name)
