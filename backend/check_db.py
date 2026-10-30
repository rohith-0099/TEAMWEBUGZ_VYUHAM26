"""Phase 3-4 diagnostic: verify Docker PostgreSQL + pgvector connection."""
import psycopg

DSN = "postgresql://trinetra:trinetra@localhost:5433/trinetra"

print("Connecting to:", DSN.replace("trinetra:trinetra", "trinetra:***"))
conn = psycopg.connect(DSN)

row = conn.execute(
    "SELECT version(), current_database(), current_user, "
    "current_setting('data_directory') AS data_dir"
).fetchone()
print(f"PostgreSQL version : {row[0]}")
print(f"Current database   : {row[1]}")
print(f"Current user       : {row[2]}")
print(f"Data directory     : {row[3]}")

avail = conn.execute(
    "SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector'"
).fetchone()
print(f"pgvector available : {avail[0]} v{avail[1]}" if avail else "pgvector NOT available")

installed = conn.execute(
    "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
).fetchone()
print(f"pgvector installed : {installed[0]} v{installed[1]}" if installed else "pgvector NOT installed yet (will be created by schema.sql)")

conn.close()
print("\nDiagnostic passed.")
