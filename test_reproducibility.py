
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATOR = ROOT / "generate_data.py"
DATABASE_NAME = "synthetic_campusresolve.db"

EXPECTED_COUNTS = {
    "tickets": 5000,
    "knowledge_articles": 200,
    "messages": 20000,
}


def find_local_dependencies():
    """
    Copy local Python modules to isolated folders.

    This avoids running the generator against
    the original CampusResolve database.
    """
    files = list(ROOT.glob("*.py"))

    if not GENERATOR.exists():
        raise FileNotFoundError(
            "generate_data.py was not found."
        )

    return files


def run_generator(destination, python_files):
    """
    Run the generator in a temporary project copy.
    """
    for source in python_files:
        shutil.copy2(
            source,
            destination / source.name
        )

    command = [
        sys.executable,
        str(destination / "generate_data.py")
    ]

    result = subprocess.run(
        command,
        cwd=destination,
        capture_output=True,
        text=True,
        timeout=180
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Generator failed:\n"
            + result.stdout
            + "\n"
            + result.stderr
        )

    database = destination / DATABASE_NAME

    if not database.exists():
        raise RuntimeError(
            "Generator did not create the expected database."
        )

    return database


def get_counts(database):
    conn = sqlite3.connect(database)

    try:
        return {
            table: conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in EXPECTED_COUNTS
        }
    finally:
        conn.close()


def database_fingerprint(database):
    """
    Calculate a logical checksum of database content.

    Unlike hashing the raw SQLite file, this compares
    stored rows and is less sensitive to SQLite file
    layout differences.
    """
    conn = sqlite3.connect(database)

    digest = hashlib.sha256()

    try:
        tables = [
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
        ]

        for table in tables:
            digest.update(
                f"TABLE:{table}\n".encode("utf-8")
            )

            columns = [
                row[1]
                for row in conn.execute(
                    f'PRAGMA table_info("{table}")'
                )
            ]

            query = (
                f'SELECT * FROM "{table}" '
                f'ORDER BY rowid'
            )

            for row in conn.execute(query):
                for column, value in zip(columns, row):
                    encoded = repr(
                        (column, value)
                    ).encode("utf-8")

                    digest.update(
                        len(encoded).to_bytes(8, "big")
                    )
                    digest.update(encoded)

                digest.update(b"\n")

        return digest.hexdigest()

    finally:
        conn.close()


def main():
    print()
    print("CampusResolve Reproducibility Test")
    print("=" * 45)
    print("Running generator twice in isolation...")
    print()

    python_files = find_local_dependencies()

    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)

        first_folder = base / "run_one"
        second_folder = base / "run_two"

        first_folder.mkdir()
        second_folder.mkdir()

        first_db = run_generator(
            first_folder,
            python_files
        )

        print("Run 1: Completed")

        second_db = run_generator(
            second_folder,
            python_files
        )

        print("Run 2: Completed")

        counts_one = get_counts(first_db)
        counts_two = get_counts(second_db)

        print()
        print("Record Count Comparison")
        print("-" * 45)

        for table in EXPECTED_COUNTS:
            print(
                f"{table}: "
                f"{counts_one[table]} vs "
                f"{counts_two[table]}"
            )

        checksum_one = database_fingerprint(
            first_db
        )

        checksum_two = database_fingerprint(
            second_db
        )

        print()
        print("Run 1 SHA-256:", checksum_one)
        print("Run 2 SHA-256:", checksum_two)

        counts_match = (
            counts_one == counts_two
            == EXPECTED_COUNTS
        )

        checksums_match = (
            checksum_one == checksum_two
        )

        print()
        print("=" * 45)

        if counts_match and checksums_match:
            print("RESULT: REPRODUCIBILITY PASSED")
            print("Same seed produced identical data.")
        else:
            print("RESULT: REPRODUCIBILITY FAILED")

            if not counts_match:
                print(
                    "Reason: Record counts differ "
                    "or do not match requirements."
                )

            if not checksums_match:
                print(
                    "Reason: Database content differs."
                )

            sys.exit(1)


if __name__ == "__main__":
    main()
