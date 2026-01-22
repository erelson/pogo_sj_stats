#!/usr/bin/env python3
"""
validate_db_schema.py - Validate database schema compatibility

Checks if a database file's schema matches the table definitions in tables.py.
This ensures the production database is compatible with the current code.

Usage:
    ./validate_db_schema.py [database_file]

    If no database file is specified, uses pogo_sj.db

Exit codes:
    0 - Schema is compatible
    1 - Schema is incompatible or validation failed
"""

import sys
from argparse import ArgumentParser
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

from tables import Base
from settings import LOCAL_DB_SPECIFIER, local_db_specifier_from_file


def validate_schema(db_path=None, verbose=False):
    """
    Validate that database schema matches SQLAlchemy model definitions.

    Args:
        db_path (str): Path to database file. If None, uses default from settings.
        verbose (bool): Print detailed information about schema

    Returns:
        bool: True if schema is compatible, False otherwise
    """
    # Connect to database
    try:
        if db_path:
            db_specifier = local_db_specifier_from_file(db_path)
            db_display = db_path
        else:
            db_specifier = LOCAL_DB_SPECIFIER
            db_display = "default database (pogo_sj.db)"

        engine = create_engine(db_specifier)
        inspector = inspect(engine)
    except OperationalError as e:
        print(f"❌ ERROR: Cannot open database: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to connect to database: {e}")
        return False

    print(f"Validating schema for: {db_display}")
    print()

    # Get actual tables in the database
    try:
        actual_tables = set(inspector.get_table_names())
    except Exception as e:
        print(f"❌ ERROR: Cannot read database tables: {e}")
        return False

    # Get expected tables from SQLAlchemy models
    expected_tables = set(Base.metadata.tables.keys())

    if verbose:
        print(f"Expected tables ({len(expected_tables)}): {sorted(expected_tables)}")
        print(f"Actual tables ({len(actual_tables)}): {sorted(actual_tables)}")
        print()

    # Check for missing tables (critical)
    missing_tables = expected_tables - actual_tables
    if missing_tables:
        print(f"❌ INCOMPATIBLE: Missing required tables")
        for table in sorted(missing_tables):
            print(f"   - {table}")
        print()
        return False

    # Check for extra tables (informational only)
    extra_tables = actual_tables - expected_tables
    if extra_tables:
        print(f"⚠️  INFO: Extra tables found (not defined in models):")
        for table in sorted(extra_tables):
            print(f"   - {table}")
        print("   This is not an error, but may indicate unused tables.")
        print()

    # Check columns for each expected table
    all_compatible = True
    column_issues = []

    for table_name in sorted(expected_tables):
        if table_name not in actual_tables:
            continue  # Already reported as missing above

        # Get actual columns from database
        try:
            actual_columns_info = inspector.get_columns(table_name)
            actual_columns = {col['name'] for col in actual_columns_info}
        except Exception as e:
            print(f"❌ ERROR: Cannot read columns for table '{table_name}': {e}")
            all_compatible = False
            continue

        # Get expected columns from model
        expected_columns = set(Base.metadata.tables[table_name].columns.keys())

        # Check for missing columns
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            all_compatible = False
            column_issues.append({
                'table': table_name,
                'type': 'missing',
                'columns': sorted(missing_columns)
            })

        # Check for extra columns (informational)
        extra_columns = actual_columns - expected_columns
        if extra_columns and verbose:
            column_issues.append({
                'table': table_name,
                'type': 'extra',
                'columns': sorted(extra_columns)
            })

        if verbose and not missing_columns and not extra_columns:
            print(f"✓ Table '{table_name}': {len(actual_columns)} columns match")

    # Report column issues
    if column_issues:
        print()
        for issue in column_issues:
            if issue['type'] == 'missing':
                print(f"❌ INCOMPATIBLE: Table '{issue['table']}' missing columns:")
                for col in issue['columns']:
                    print(f"   - {col}")
            elif issue['type'] == 'extra':
                print(f"⚠️  INFO: Table '{issue['table']}' has extra columns:")
                for col in issue['columns']:
                    print(f"   - {col}")
        print()

    # Final result
    if all_compatible:
        print("=" * 70)
        print("✓ SCHEMA COMPATIBLE: Database schema matches table definitions")
        print("=" * 70)
        return True
    else:
        print("=" * 70)
        print("❌ SCHEMA INCOMPATIBLE: Database schema does not match")
        print("=" * 70)
        print()
        print("This may cause errors when running the application.")
        print("You may need to:")
        print("  1. Run database migrations to update the schema")
        print("  2. Use an older version of the code")
        print("  3. Regenerate the database from scratch")
        return False


def main():
    """Main entry point"""
    parser = ArgumentParser(
        description="Validate database schema compatibility",
        epilog="Exit code 0 = compatible, 1 = incompatible"
    )
    parser.add_argument(
        "database",
        nargs='?',
        default=None,
        help="Path to database file (default: pogo_sj.db)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed information about schema"
    )

    args = parser.parse_args()

    # Run validation
    is_compatible = validate_schema(args.database, verbose=args.verbose)

    # Exit with appropriate code
    sys.exit(0 if is_compatible else 1)


if __name__ == '__main__':
    main()
