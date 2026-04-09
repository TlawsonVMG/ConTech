import argparse
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - the project requirements install this.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "backups"


def _load_environment():
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")


def _timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _find_pg_dump():
    found = shutil.which("pg_dump")
    if found:
        return Path(found)

    postgresql_root = Path("C:/Program Files/PostgreSQL")
    if postgresql_root.exists():
        candidates = sorted(postgresql_root.glob("*/bin/pg_dump.exe"), reverse=True)
        if candidates:
            return candidates[0]

    raise RuntimeError("pg_dump was not found. Install PostgreSQL client tools or add PostgreSQL bin to PATH.")


def _backup_postgresql(database_url, backup_dir):
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL is not PostgreSQL.")

    pg_dump = _find_pg_dump()
    dump_path = backup_dir / "contech-postgresql.dump"
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": parsed.hostname or "localhost",
            "PGPORT": str(parsed.port or 5432),
            "PGUSER": unquote(parsed.username or ""),
            "PGDATABASE": (parsed.path or "/").lstrip("/"),
        }
    )
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)

    subprocess.run(
        [str(pg_dump), "--format=custom", "--file", str(dump_path)],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )
    return dump_path


def _backup_sqlite(database_path, backup_dir):
    source = Path(database_path)
    if not source.exists():
        raise RuntimeError(f"SQLite database was not found at {source}.")
    target = backup_dir / source.name
    shutil.copy2(source, target)
    return target


def _zip_uploads(upload_path, backup_dir):
    upload_root = Path(upload_path)
    zip_path = backup_dir / "job-document-uploads.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        if upload_root.exists():
            for file_path in upload_root.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(upload_root))

    return zip_path


def _write_manifest(backup_dir, database_artifact, upload_artifact):
    manifest = backup_dir / "manifest.txt"
    manifest.write_text(
        "\n".join(
            [
                "ConTech backup",
                f"Created at: {datetime.now().isoformat(timespec='seconds')}",
                f"Database artifact: {database_artifact.name}",
                f"Upload artifact: {upload_artifact.name}",
                "Restore note: restore the database dump first, then unzip uploads into instance/uploads/job-documents.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Create a local ConTech database and upload backup.")
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT), help="Directory where timestamped backups are stored.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL for PostgreSQL backups.")
    parser.add_argument("--sqlite-path", default=None, help="Override the SQLite database path when not using PostgreSQL.")
    parser.add_argument(
        "--uploads",
        default=str(PROJECT_ROOT / "instance" / "uploads" / "job-documents"),
        help="Job-document uploads directory to archive.",
    )
    args = parser.parse_args()

    _load_environment()
    backup_dir = Path(args.backup_root) / f"contech-{_timestamp()}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if database_url and urlparse(database_url).scheme in {"postgresql", "postgres"}:
        database_artifact = _backup_postgresql(database_url, backup_dir)
    else:
        sqlite_path = args.sqlite_path or os.getenv("DATABASE") or str(PROJECT_ROOT / "instance" / "contech.sqlite3")
        database_artifact = _backup_sqlite(sqlite_path, backup_dir)

    upload_artifact = _zip_uploads(args.uploads, backup_dir)
    manifest = _write_manifest(backup_dir, database_artifact, upload_artifact)

    print(f"Backup created: {backup_dir}")
    print(f"Database artifact: {database_artifact}")
    print(f"Upload artifact: {upload_artifact}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
