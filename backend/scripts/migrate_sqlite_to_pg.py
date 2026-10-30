"""
Safe and repeatable SQLite-to-PostgreSQL migration utility.

Production Safety Guarantees:
1. Strict Preflight Verification: All 18 destination tables must be completely empty (0 records).
2. Abort-On-Data Rule: If any table contains even one record, the migration is aborted immediately.
   Tables are NEVER silently skipped.
3. Fail-Closed Error Handling: Query errors or missing tables are reported and trigger aborts.
   Errors are NEVER interpreted as zero records.
4. Single-Transaction Rollback: The entire migration runs in one transaction context. Any failure
   rolls back the entire destination database.
5. Strict Count Verification: Hard assertions verify that destination row counts match source row counts
   for all 18 tables before committing.
6. Sequences Synchronized: PostgreSQL auto-increment sequences are synchronized to MAX(id).
7. Read-Only Dry-Run: Dry-run mode never writes to the target or modifies data.
8. No Destructive Actions: Does not delete or truncate any existing data.

Usage:
    python backend/scripts/migrate_sqlite_to_pg.py [--sqlite-path PATH] [--pg-url URL] [--dry-run] [--preflight-only]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, Table, MetaData, inspect
from sqlalchemy.engine import Engine, Connection

from app.database import Base, _normalize_database_url
import app.models  # noqa: F401 - registers all models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sqlite_to_pg_migration")

# Topological dependency order (parent tables before child tables)
TABLE_MIGRATION_ORDER: List[str] = [
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


class MigrationError(Exception):
    """Base exception for migration failures."""
    pass


class MigrationPreflightError(MigrationError):
    """Raised when preflight safety checks fail (non-empty destination, missing tables, failed queries)."""
    pass


class MigrationVerificationError(MigrationError):
    """Raised when post-migration row count verification fails."""
    pass


def preflight_verify(
    sqlite_conn: Connection,
    pg_engine: Engine,
    tables: List[str] = TABLE_MIGRATION_ORDER,
) -> Dict[str, int]:
    """Strict preflight safety check:
    1. Verify all required tables exist in the source SQLite database.
    2. Ensure destination schema exists.
    3. Verify that ALL destination tables are completely empty (0 records).
    4. Abort on any query failure — never interpret errors as 0 records.
    """
    logger.info("Executing preflight verification...")

    # 1. Source verification
    sqlite_meta = MetaData()
    try:
        sqlite_meta.reflect(bind=sqlite_conn)
    except Exception as e:
        raise MigrationPreflightError(f"Failed to inspect SQLite source database: {e}") from e

    missing_source = [t for t in tables if t not in sqlite_meta.tables]
    if missing_source:
        raise MigrationPreflightError(
            f"Preflight failed: Required table(s) missing from source SQLite: {', '.join(missing_source)}"
        )

    # 2. Destination schema initialization (ensure tables exist to inspect)
    try:
        Base.metadata.create_all(bind=pg_engine)
    except Exception as e:
        raise MigrationPreflightError(f"Failed to ensure destination schema exists: {e}") from e

    # 3. Inspect destination tables
    pg_meta = MetaData()
    try:
        pg_meta.reflect(bind=pg_engine)
    except Exception as e:
        raise MigrationPreflightError(f"Failed to inspect destination PostgreSQL tables: {e}") from e

    missing_dest = [t for t in tables if t not in pg_meta.tables]
    if missing_dest:
        raise MigrationPreflightError(
            f"Preflight failed: Required table(s) missing from destination database: {', '.join(missing_dest)}"
        )

    # 4. Check that all destination tables are strictly empty
    non_empty_tables: Dict[str, int] = {}
    with pg_engine.connect() as pg_conn:
        for table_name in tables:
            try:
                cnt = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            except Exception as e:
                # Query failure must never be swallowed or treated as zero
                raise MigrationPreflightError(
                    f"Preflight failed: Database query failed while checking destination table '{table_name}': {e}. "
                    f"Query errors are never treated as zero records."
                ) from e

            if cnt is None:
                raise MigrationPreflightError(
                    f"Preflight failed: NULL count returned for destination table '{table_name}'."
                )

            if cnt > 0:
                non_empty_tables[table_name] = cnt

    if non_empty_tables:
        details = ", ".join(f"'{tbl}' ({count} rows)" for tbl, count in non_empty_tables.items())
        raise MigrationPreflightError(
            f"Migration aborted for production safety: Destination database is not empty. "
            f"Found existing records in {len(non_empty_tables)} table(s): {details}. "
            f"Never silently skip tables. The destination database must be completely empty before migration."
        )

    logger.info("Preflight verification PASSED: All %d destination tables are completely empty.", len(tables))

    # Return source row counts
    source_counts: Dict[str, int] = {}
    for table_name in tables:
        try:
            cnt = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            source_counts[table_name] = cnt
        except Exception as e:
            raise MigrationPreflightError(f"Failed to count rows in source table '{table_name}': {e}") from e

    return source_counts


def migrate(
    sqlite_path: str,
    pg_url: str,
    batch_size: int = 500,
    dry_run: bool = False,
    preflight_only: bool = False,
) -> Dict[str, int]:
    """Execute production-safe migration from SQLite to PostgreSQL with atomic rollback and count assertions."""
    sqlite_file = Path(sqlite_path).resolve()
    if not sqlite_file.exists():
        raise FileNotFoundError(f"SQLite database file not found at: {sqlite_file}")

    sqlite_engine = create_engine(f"sqlite:///{sqlite_file}", connect_args={"check_same_thread": False})
    norm_pg_url = _normalize_database_url(pg_url)
    pg_engine = create_engine(norm_pg_url, pool_pre_ping=True)

    logger.info("Source SQLite: %s", sqlite_file)
    logger.info("Target Dialect: %s (%s)", pg_engine.dialect.name, norm_pg_url.split("@")[-1])

    # 1. Dry-run mode: read-only inspection of source
    if dry_run:
        logger.info("Executing DRY-RUN inspection (read-only)...")
        source_counts: Dict[str, int] = {}
        with sqlite_engine.connect() as sqlite_conn:
            sqlite_meta = MetaData()
            sqlite_meta.reflect(bind=sqlite_conn)
            missing = [t for t in TABLE_MIGRATION_ORDER if t not in sqlite_meta.tables]
            if missing:
                raise MigrationPreflightError(f"Required table(s) missing from source SQLite: {', '.join(missing)}")

            for table_name in TABLE_MIGRATION_ORDER:
                cnt = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
                source_counts[table_name] = cnt
                logger.info("Table '%s': %d records found in source", table_name, cnt)

        logger.info("DRY-RUN completed. Total tables inspected: %d", len(source_counts))
        return source_counts

    # 2. Preflight verification: verify source and target emptiness
    with sqlite_engine.connect() as sqlite_conn:
        source_counts = preflight_verify(sqlite_conn=sqlite_conn, pg_engine=pg_engine)

    if preflight_only:
        logger.info("Preflight check completed successfully. No migration executed.")
        return source_counts

    # 3. Single-transaction live migration
    logger.info("Beginning single-transaction migration for %d tables...", len(TABLE_MIGRATION_ORDER))
    migration_counts: Dict[str, int] = {}

    sqlite_meta = MetaData()
    with sqlite_engine.connect() as sqlite_conn:
        sqlite_meta.reflect(bind=sqlite_conn)

        pg_meta = MetaData()
        pg_meta.reflect(bind=pg_engine)

        # Execute all table insertions and assertions within a single atomic transaction
        with pg_engine.begin() as pg_conn:
            for table_name in TABLE_MIGRATION_ORDER:
                src_table = sqlite_meta.tables[table_name]
                dst_table = pg_meta.tables[table_name]
                src_count = source_counts[table_name]

                logger.info("Migrating table '%s' (%d records)...", table_name, src_count)
                if src_count == 0:
                    migration_counts[table_name] = 0
                    continue

                # Stream and insert in batches
                result = sqlite_conn.execute(src_table.select())
                columns = [c.name for c in src_table.columns]

                total_inserted = 0
                while True:
                    rows = result.fetchmany(batch_size)
                    if not rows:
                        break

                    chunk = [dict(zip(columns, row)) for row in rows]
                    if chunk:
                        pg_conn.execute(dst_table.insert(), chunk)
                        total_inserted += len(chunk)

                migration_counts[table_name] = total_inserted
                logger.info("Table '%s': inserted %d records", table_name, total_inserted)

                # Sequence synchronization for PostgreSQL
                if pg_engine.dialect.name == "postgresql":
                    try:
                        seq_query = text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                            f"COALESCE(MAX(id), 1), true) FROM {table_name}"
                        )
                        pg_conn.execute(seq_query)
                    except Exception as seq_err:
                        # Log but do not fail if table does not use serial id
                        logger.debug("Sequence sync skipped for table '%s': %s", table_name, seq_err)

            # 4. Hard post-migration count assertions across ALL 18 tables before transaction commit
            logger.info("Executing post-migration row-count assertions across all 18 tables...")
            for table_name in TABLE_MIGRATION_ORDER:
                expected = source_counts[table_name]
                try:
                    actual = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                except Exception as e:
                    raise MigrationVerificationError(
                        f"Post-migration check failed: Could not query count for '{table_name}': {e}. "
                        f"Transaction will be rolled back."
                    ) from e

                if actual != expected:
                    raise MigrationVerificationError(
                        f"Post-migration verification FAILED for table '{table_name}': "
                        f"source={expected}, destination={actual}. "
                        f"Transaction will be rolled back."
                    )
                logger.info("Verification PASSED for '%s': %d == %d", table_name, expected, actual)

    logger.info("Migration and verification successfully completed! All %d tables match 100%%.", len(TABLE_MIGRATION_ORDER))
    return migration_counts


def main():
    parser = argparse.ArgumentParser(description="Production-safe SQLite to PostgreSQL migration utility.")
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
    parser.add_argument("--preflight-only", action="store_true", help="Run preflight checks only without migrating")

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
            preflight_only=args.preflight_only,
        )
        mode = "DRY-RUN INSPECTION" if args.dry_run else ("PREFLIGHT CHECK" if args.preflight_only else "MIGRATION SUMMARY")
        print(f"\n=== {mode} ===")
        for tbl, cnt in counts.items():
            print(f"  {tbl:<28}: {cnt:>6} rows")
        print("=" * (len(mode) + 8))
    except Exception as e:
        logger.exception("Migration failed: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
