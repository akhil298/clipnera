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

4. Initialize tables:

```bash
pip install -r requirements.txt
python init_db.py
```

## Option 2: Using Docker

```bash
docker run --name clipnera-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=clipnera -p 5432:5432 -d postgres:16
python init_db.py
```

## Verify Connection

```bash
python -c "import asyncio; from init_db import init_db; asyncio.run(init_db())"
```
