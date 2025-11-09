#!/usr/bin/env python3
import subprocess
from datetime import datetime, timezone

from sys_scripts.utils import (
    Context,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    BACKUP_DB_FILE,
)

"""Safe restore script (high level)

Steps performed:
1) Validate backup file exists and is non-empty.
2) Create a temporary database and restore the SQL dump into it.
3) Run sequence synchronization to ensure serials are correct.
4) Swap the temporary database into place by dropping the old DB and renaming the temp.

This approach preserves the existing database until the restore is validated.
"""

# -------------------------------------------------------------------
# RESTORE LOGIC (Safe -- restore to temp DB then swap)
# -------------------------------------------------------------------
def restore_database():
    ctx = Context("restore")
    ctx.log("=== Distributor Database Restore (SAFE) ===", append=False)
    
    entered_maintenance = False
    # prepare temp DB name early so cleanup can reference it even on early failures
    TEMP_DB = f"{DB_NAME}_restore_tmp"

    if ctx.is_maintaining():
        ctx.log("Aborting: maintenance already in progress (found .maintaining).")
        raise RuntimeError("Another maintenance process is active. Could not start the process.")
    
    ctx.start_processing()
    entered_maintenance = True

    ctx.load_env()
    db_container = ctx.get_db_container()

    try:
        # Validate backup file
        if not BACKUP_DB_FILE.exists():
            raise FileNotFoundError(f"No backup file found at {BACKUP_DB_FILE}")
        if BACKUP_DB_FILE.stat().st_size == 0:
            raise RuntimeError(f"Backup file is empty: {BACKUP_DB_FILE}")

        ctx.log(f"Restoring database '{DB_NAME}' from {BACKUP_DB_FILE} using container '{db_container}'...")

        # Helper: run command with logging
        def run(cmd, stdin=None, input=None, allow_error=False, quiet=False):
            # Ensure we operate on a mutable copy
            cmd_list = list(cmd)
            # If this is a docker exec invocation, inject PGPASSWORD into the exec env
            try:
                if len(cmd_list) >= 2 and cmd_list[0] == "docker" and cmd_list[1] == "exec":
                    if "-e" not in cmd_list:
                        cmd_list = cmd_list[:2] + ["-e", f"PGPASSWORD={DB_PASSWORD}"] + cmd_list[2:]
            except Exception:
                # If something unexpected happens, fall back to original cmd
                cmd_list = list(cmd)

            proc = subprocess.run(cmd_list, stdin=stdin, input=input, capture_output=True, text=True)
            if not quiet and proc.stdout and proc.stdout.strip():
                ctx.log(proc.stdout.strip())
            if proc.returncode != 0:
                if allow_error:
                    ctx.log(proc.stderr.strip() or "Command failed (ignored).")
                else:
                    ctx.log(proc.stderr.strip() or "Command failed.")
                    raise RuntimeError(proc.stderr or "Command failed.")
            return proc

        # ---------------------------------------------------------------
        # 1) Terminate active connections to the target DB (best-effort)
        # ---------------------------------------------------------------
        terminate_sql = (
            "SELECT pg_terminate_backend(pid) "
            f"FROM pg_stat_activity WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();"
        )
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", terminate_sql
        ], allow_error=True, quiet=True)

        # ---------------------------------------------------------------
        # 2) Create temporary database for restore
        # ---------------------------------------------------------------
        # TEMP_DB was defined earlier to ensure cleanup paths can reference it.
        ctx.log(f"Preparing temporary restore database '{TEMP_DB}'...")

        # Drop any leftover temp DB (safe cleanup)
        drop_tmp_sql = f"DROP DATABASE IF EXISTS {TEMP_DB} WITH (FORCE);"
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", drop_tmp_sql
        ], quiet=True)

        # Create fresh temp DB
        create_tmp_sql = f"CREATE DATABASE {TEMP_DB} OWNER {DB_USER};"
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", create_tmp_sql
        ], quiet=True)

        # ---------------------------------------------------------------
        # 3) Restore SQL dump into temporary DB
        # ---------------------------------------------------------------
        ctx.log("Restoring SQL dump into temporary database...")
        with open(BACKUP_DB_FILE, "r", encoding="utf-8") as f:
            run([
                "docker", "exec", "-i", db_container,
                "psql", "-q", "-U", DB_USER, "-d", TEMP_DB, "-v", "ON_ERROR_STOP=1"
            ], stdin=f, quiet=True)

        ctx.log("SQL restore to temporary database completed successfully.")

        # ---------------------------------------------------------------
        # 4) Sequence auto-fix on temp DB
        # ---------------------------------------------------------------
        ctx.log("Running sequence auto-fix on temporary database...")
        seq_fix_sql = r"""
DO $$
DECLARE
    r RECORD;
    max_id BIGINT;
    full_seq_name text;
BEGIN
  FOR r IN
    SELECT
      n.nspname   AS seq_schema,
      s.relname   AS seq_name,
      t.relname   AS table_name,
      a.attname   AS column_name
    FROM pg_class s
    JOIN pg_namespace n ON n.oid = s.relnamespace
    JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
    JOIN pg_class t ON t.oid = d.refobjid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
    WHERE s.relkind = 'S'
      AND n.nspname = 'public'
  LOOP
    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I.%I',
                   r.column_name, r.seq_schema, r.table_name)
      INTO max_id;

    full_seq_name := quote_ident(r.seq_schema) || '.' || quote_ident(r.seq_name);

    IF max_id = 0 THEN
      EXECUTE format('SELECT setval(%s, 1, false)', quote_literal(full_seq_name));
    ELSE
      EXECUTE format('SELECT setval(%s, %s, true)', quote_literal(full_seq_name), max_id + 1);
    END IF;
  END LOOP;
END$$;
"""
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", TEMP_DB, "-v", "ON_ERROR_STOP=1"
        ], input=seq_fix_sql, quiet=True)

        ctx.log("Sequences synchronized in temporary database.")

        # ---------------------------------------------------------------
        # 5) Swap databases: terminate connections -> drop old -> rename temp
        # ---------------------------------------------------------------
        ctx.log("Swapping restored database into place...")

        # Terminate connections to the old DB
        terminate_sql = (
            "SELECT pg_terminate_backend(pid) "
            f"FROM pg_stat_activity WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();"
        )
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", terminate_sql
        ], allow_error=True, quiet=True)

        # Drop the old database (now that temp is validated)
        drop_db_sql = f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);"
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", drop_db_sql
        ], quiet=True)

        # Rename the temp DB to the real name
        rename_sql = f"ALTER DATABASE {TEMP_DB} RENAME TO {DB_NAME};"
        run([
            "docker", "exec", "-i", db_container,
            "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
            "-c", rename_sql
        ], quiet=True)

        ctx.log("Swapped temporary database into place successfully.")
        ctx.update_sys_data("last_restore", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        ctx.log("Database restore completed successfully.")

    except Exception as e:
        # Keep this verbose so you can debug why the restore failed
        ctx.log(f"Restore failed: {e}")

        # Attempt cleanup of temp DB if it exists (best-effort)
        try:
            ctx.log("Attempting to remove temporary database (best-effort)...")
            run([
                "docker", "exec", "-i", db_container,
                "psql", "-q", "-U", DB_USER, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
                "-c", f"DROP DATABASE IF EXISTS {TEMP_DB} WITH (FORCE);"
            ], quiet=True, allow_error=True)
            ctx.log("Temporary database removed (if present).")
        except Exception:
            # ignore cleanup errors, original DB remains intact
            pass

    finally:
        # Only end processing if we successfully started maintenance.
        try:
            if entered_maintenance:
                ctx.end_processing()
        except Exception as e:
            # Log any cleanup issues but don't mask the original exception.
            ctx.log(f"Error during end_processing(): {e}")
        ctx.log("-" * 60)

# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    restore_database()
