
import csv
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "synthetic_campusresolve.db"
EXPORT_DIR = ROOT / "exports"

# All 15 CampusResolve database tables
TABLES = [
    "roles",
    "terms",
    "categories",
    "requesters",
    "policy_documents",
    "knowledge_articles",
    "routing_rules",
    "sla_business_hours",
    "tickets",
    "messages",
    "assignments",
    "sla",
    "resolution_feedback",
    "ticket_events",
    "policy_citations",
]

SEED = 20261022


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def get_connection():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    connection = sqlite3.connect(
        f"file:{DATABASE.as_posix()}?mode=ro",
        uri=True
    )
    connection.row_factory = sqlite3.Row
    return connection


def get_table_names(connection):
    rows = connection.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
    """).fetchall()

    return {row["name"] for row in rows}


def get_rows(connection, table):
    safe_table = quote_identifier(table)

    cursor = connection.execute(
        f"SELECT * FROM {safe_table} ORDER BY rowid"
    )

    columns = [
        item[0]
        for item in cursor.description
    ]

    rows = [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

    return columns, rows


def export_csv(table, columns, rows):
    output = EXPORT_DIR / f"{table}.csv"

    with output.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns
        )
        writer.writeheader()
        writer.writerows(rows)

    return output


def export_json(table, rows):
    output = EXPORT_DIR / f"{table}.json"

    with output.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            rows,
            file,
            indent=2,
            ensure_ascii=False
        )

    return output


def export_sql(connection):
    output = EXPORT_DIR / "synthetic_seed.sql"

    with output.open(
        "w", encoding="utf-8"
    ) as file:
        for statement in connection.iterdump():
            file.write(statement)
            file.write("\n")

    return output


def checksum(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(block)

    return digest.hexdigest()


def main():
    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = get_connection()

    try:
        existing_tables = get_table_names(
            connection
        )

        missing = [
            table
            for table in TABLES
            if table not in existing_tables
        ]

        if missing:
            raise RuntimeError(
                "Missing required tables: "
                + ", ".join(missing)
            )

        exported_files = []
        table_counts = {}

        print()
        print("CampusResolve Data Export")
        print("=" * 48)

        for table in TABLES:
            columns, rows = get_rows(
                connection, table
            )

            csv_path = export_csv(
                table, columns, rows
            )

            json_path = export_json(
                table, rows
            )

            exported_files.extend([
                csv_path,
                json_path
            ])

            table_counts[table] = len(rows)

            print(
                f"[OK] {table}: "
                f"{len(rows)} records"
            )

        sql_path = export_sql(connection)
        exported_files.append(sql_path)

        manifest = {
            "project": "CampusResolve",
            "seed": SEED,
            "source_database": DATABASE.name,
            "total_tables": len(TABLES),
            "table_counts": table_counts,
            "files": {}
        }

        for path in exported_files:
            manifest["files"][path.name] = {
                "sha256": checksum(path),
                "size_bytes": path.stat().st_size
            }

        manifest_path = (
            EXPORT_DIR / "export_manifest.json"
        )

        with manifest_path.open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(
                manifest,
                file,
                indent=2
            )

        print("=" * 48)
        print(
            "Tables exported:",
            len(TABLES)
        )
        print(
            "Exported data files:",
            len(exported_files)
        )
        print(
            "Manifest:",
            manifest_path.name
        )
        print(
            "Output folder:",
            EXPORT_DIR
        )
        print("RESULT: EXPORT COMPLETED")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
