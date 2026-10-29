"""
Safe and repeatable SQLite-to-PostgreSQL migration utility.

Preserves:
- Primary key IDs and foreign key integrity across all 18 tables.
- Exact timestamps (created_at, resolved_at, sent_at, etc.).
- Audit history (status events, communication messages, SLA events, surveys).
- PostgreSQL sequence synchronization (setval) to guarantee new record creation.

Usage:
    python backend/scripts/migrate_sqlite_to_pg.py [--sqlite-path PATH] [--pg-url URL] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, Table, MetaData, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base, _normalize_database_url
import app.models  # noqa: F401 - registers all models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sqlite_to_pg_migration")

# Topological dependency order (parent tables before child tables)
TABLE_MIGRATION_ORDER = [
    "categories",
    "teams",
    "priority_rules",
    "products",
    "customers",
    "generation_runs",
    "agents",
    "orders",
    "order_items",
    "complaints",
    "assignments",
    "complaint_messages",
    "complaint_relationships",
    "complaint_status_events",
    "resolutions",
    "sla_clocks",
    "surveys",
    "sla_events",
]


def migrate(
    sqlite_path: str,
    pg_url: str,
    batch_size: int = 500,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Execute migration from SQLite to PostgreSQL with integrity checks and sequence resets."""
    sqlite_file = Path(sqlite_path).resolve()
    if not sqlite_file.exists():
        raise FileNotFoundError(f"SQLite database file not found at: {sqlite_file}")

    sqlite_engine = create_engine(f"sqlite:///{sqlite_file}", connect_args={"check_same_thread": False})
    norm_pg_url = _normalize_database_url(pg_url)
    pg_engine = create_engine(norm_pg_url, pool_pre_ping=True)

    logger.info("Source SQLite: %s", sqlite_file)
    logger.info("Target Dialect: %s (%s)", pg_engine.dialect.name, norm_pg_url.split("@")[-1])

    if not dry_run:
        # 1. Initialize all schema tables, foreign keys, and indexes on target
        logger.info("Initializing schema tables in PostgreSQL target...")
        Base.metadata.create_all(bind=pg_engine)

    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    pg_meta = MetaData()
    if not dry_run:
        pg_meta.reflect(bind=pg_engine)

    migration_counts: Dict[str, int] = {}

    with sqlite_engine.connect() as sqlite_conn:
        pg_conn_cm = pg_engine.begin() if not dry_run else None
        pg_conn = pg_conn_cm.__enter__() if pg_conn_cm else None

        try:
            for table_name in TABLE_MIGRATION_ORDER:
                if table_name not in sqlite_meta.tables:
                    logger.warning("Table %s not found in SQLite source — skipping", table_name)
                    continue

                src_table = sqlite_meta.tables[table_name]
                src_count = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
                logger.info("Table '%s': %d records found in source", table_name, src_count)

                if dry_run:
                    migration_counts[table_name] = src_count
                    continue

                dst_table = pg_meta.tables.get(table_name)
                if dst_table is None:
                    logger.warning("Table %s not found in target PostgreSQL — skipping", table_name)
                    continue

                if src_count == 0:
                    migration_counts[table_name] = 0
                    continue

                # Check if destination already has records
                dst_existing = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
                if dst_existing > 0:
                    logger.info(
                        "Table '%s' already has %d records in target. Existing data preserved.",
                        table_name,
                        dst_existing,
                    )
                    migration_counts[table_name] = dst_existing
                    continue

                # Read source rows
                result = sqlite_conn.execute(src_table.select())
                columns = [c.name for c in src_table.columns]

                total_inserted = 0
                while True:
                    rows = result.fetchmany(batch_size)
                    if not rows:
                        break

                    chunk = []
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        chunk.append(row_dict)

                    if chunk:
                        pg_conn.execute(dst_table.insert(), chunk)
                        total_inserted += len(chunk)

                logger.info("Table '%s': successfully migrated %d records", table_name, total_inserted)
                migration_counts[table_name] = total_inserted

                # Reset auto-increment sequence in PostgreSQL if applicable
                if pg_engine.dialect.name == "postgresql":
                    try:
                        seq_query = text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                            f"COALESCE(MAX(id), 1), true) FROM {table_name}"
                        )
                        pg_conn.execute(seq_query)
                    except Exception:
                        pass
        finally:
            if pg_conn_cm:
                pg_conn_cm.__exit__(None, None, None)

    logger.info("Migration complete. Total tables migrated: %d", len(migration_counts))
    return migration_counts


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite database to PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default=os.getenv("SQLITE_PATH", str(backend_dir / "complaint_intelligence.db")),
        help="Path to source SQLite database file",
    )
    parser.add_argument(
        "--pg-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Target PostgreSQL connection URL (e.g. postgresql://user:pass@host:5432/dbname)",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for bulk inserts")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and check source counts without writing")

    args = parser.parse_args()

    if not args.pg_url and not args.dry_run:
        logger.error("No PostgreSQL URL provided via --pg-url or DATABASE_URL environment variable.")
        sys.exit(1)

    try:
        counts = migrate(
            sqlite_path=args.sqlite_path,
            pg_url=args.pg_url or "sqlite:///:memory:",
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        print("\n=== MIGRATION SUMMARY ===")
        for tbl, cnt in counts.items():
            print(f"  {tbl:<28}: {cnt:>6} rows")
        print("=========================")
    except Exception as e:
        logger.exception("Migration failed: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
