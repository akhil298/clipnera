# Database Setup

## Option 1: Using PostgreSQL (Recommended)

1. Install PostgreSQL: https://www.postgresql.org/download/windows/
2. Open **SQL Shell (psql)** or **pgAdmin**
3. Run these commands:

```sql
CREATE DATABASE clipnera;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE clipnera TO postgres;
```

4. Initialize tables and migrations:

```bash
pip install -r requirements.txt
python init_db.py
```

## Option 2: Using Docker

```bash
docker run --name clipnera-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=clipnera -p 5432:5432 -d postgres:16
python init_db.py
```

## Migrations

This project uses **Alembic** for database migrations. Migrations run automatically on app startup, but you can also manage them manually.

### Auto-migration on startup

The FastAPI lifespan in `main.py` runs `alembic upgrade head` automatically when the server starts. Any pending schema changes (new columns, type updates, enums) are applied on restart.

### Manual migration commands

Generate a new migration after changing models:

```bash
alembic revision --autogenerate -m "add_new_column"
alembic upgrade head
```

Apply pending migrations:

```bash
alembic upgrade head
```

Rollback the last migration:

```bash
alembic downgrade -1
```

View current migration state:

```bash
alembic current
```

View migration history:

```bash
alembic history
```

### Existing databases

If you already have tables from the old `init_db.py` and need to adopt migrations:

```bash
alembic stamp head
```

This marks the current database state as the latest migration without running any SQL. After stamping, future model changes will generate proper migrations.

### First run on an existing database

If the initial migration fails with "relation already exists", the migration is now idempotent with `IF NOT EXISTS`, but if you still see issues, run:

```bash
alembic stamp head
```

Then restart the app.

### Supported changes

Alembic autogenerate detects:
- New columns added to existing tables
- Column data type changes
- Enum value additions
- New tables
- Table and column renames (with some limitations)

For complex changes (enum removals, column drops), review and edit the generated migration before applying.
