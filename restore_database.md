# Database Restoration Guide

## Problem
Only the 3 survey tables exist in the database. All other tables are missing.

## Solution: Restore All Tables

### Option 1: If you have a database backup
Restore from backup - this is the safest option if available.

### Option 2: Re-run all migrations from scratch

**Step 1: Check current Alembic version in database**
```sql
SELECT * FROM alembic_version;
```

**Step 2: If alembic_version table exists and shows 001_add_survey_tables:**
```bash
# Downgrade the survey migration
alembic downgrade f9218dd57616

# Then stamp to base
alembic stamp base

# Then upgrade all
alembic upgrade head
```

**Step 3: If alembic_version table doesn't exist or is empty:**
```bash
# Stamp to base (tells Alembic no migrations have been run)
alembic stamp base

# Then upgrade all migrations
alembic upgrade head
```

**Step 4: If the survey tables are causing conflicts:**
```sql
-- Manually drop survey tables if needed
DROP TABLE IF EXISTS survey_responses CASCADE;
DROP TABLE IF EXISTS survey_invites CASCADE;
DROP TABLE IF EXISTS surveys CASCADE;
DROP TYPE IF EXISTS surveystatus;

-- Then delete the version record
DELETE FROM alembic_version WHERE version_num = '001_add_survey_tables';
```

Then run:
```bash
alembic stamp base
alembic upgrade head
```

## Important Notes

- **Backup first**: Always backup your database before running migrations
- The survey migration will be re-applied at the end, which is safe (it only creates tables)
- All previous migrations will create the missing tables (accounts, users, schemas, etc.)









