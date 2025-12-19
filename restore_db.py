"""
Database Restoration Script

This script helps restore all database tables by:
1. Checking current state
2. Dropping survey tables if they're the only ones
3. Resetting Alembic version tracking
4. Running all migrations from scratch
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in environment")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def check_tables():
    """Check what tables exist in the database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables

def check_alembic_version():
    """Check Alembic version table."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            row = result.fetchone()
            if row:
                return row[0]
            return None
    except Exception as e:
        print(f"alembic_version table doesn't exist or error: {e}")
        return None

def drop_survey_tables():
    """Drop survey tables if they exist."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS survey_responses CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS survey_invites CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS surveys CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS surveystatus"))
        conn.commit()
        print("✓ Dropped survey tables")

def reset_alembic_version():
    """Reset Alembic version tracking."""
    with engine.connect() as conn:
        # Drop alembic_version table if it exists
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
        print("✓ Reset Alembic version tracking")

def main():
    print("=" * 60)
    print("DATABASE RESTORATION SCRIPT")
    print("=" * 60)
    
    # Check current state
    print("\n[1] Checking current database state...")
    tables = check_tables()
    print(f"   Found {len(tables)} tables: {tables}")
    
    alembic_version = check_alembic_version()
    if alembic_version:
        print(f"   Current Alembic version: {alembic_version}")
    else:
        print("   No Alembic version found")
    
    # Check if only survey tables exist
    survey_tables = {'surveys', 'survey_invites', 'survey_responses'}
    other_tables = set(tables) - survey_tables - {'alembic_version'}
    
    if len(other_tables) == 0 and len(survey_tables & set(tables)) > 0:
        print("\n[2] Only survey tables found. Dropping them...")
        drop_survey_tables()
    else:
        print("\n[2] Other tables found. Skipping survey table drop.")
        print(f"   Other tables: {other_tables}")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Reset Alembic version
    print("\n[3] Resetting Alembic version tracking...")
    reset_alembic_version()
    
    print("\n[4] Next steps:")
    print("   Run: alembic stamp base")
    print("   Then: alembic upgrade head")
    print("\n" + "=" * 60)
    print("Script completed. Please run the Alembic commands above.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)









