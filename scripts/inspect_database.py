import argparse
from pathlib import Path

import duckdb

parser = argparse.ArgumentParser(description="Inspect an NBA DuckDB database")
parser.add_argument("database", type=Path)
args = parser.parse_args()

if not args.database.exists():
    raise SystemExit(f"File not found: {args.database}")

db = duckdb.connect(str(args.database), read_only=True)
tables = db.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema='main' ORDER BY table_name
""").fetchall()

print(f"Database: {args.database}")
print(f"Size: {args.database.stat().st_size:,} bytes")
print(f"Tables/views: {len(tables)}")

interesting = ("player_game", "dim_player", "dim_game", "analytics_player")
for (table,) in tables:
    if any(term in table.lower() for term in interesting):
        columns = db.execute(f'DESCRIBE "{table}"').fetchall()
        count = db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        print(f"\n{table} ({count:,} rows)")
        print("  " + ", ".join(row[0] for row in columns))
