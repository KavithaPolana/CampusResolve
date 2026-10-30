
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from sla_engine import calculate_sla_deadlines


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "synthetic_campusresolve.db"

EXPECTED_COUNTS = {
    "tickets": 5000,
    "knowledge_articles": 200,
    "messages": 20000,
}

VALID_STATUSES = {
    "Open",
    "Assigned",
    "In Progress",
    "Escalated",
    "Resolved",
    "Closed",
}

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def connect():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    conn = sqlite3.connect(
        f"file:{DATABASE.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_tables(conn):
    return {
        row["name"]
        for row in conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)
    }


def check_counts(conn):
    errors = []

    for table, expected in EXPECTED_COUNTS.items():
        actual = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        if actual != expected:
            errors.append(
                f"{table}: expected {expected}, got {actual}"
            )

    return errors


def check_foreign_keys(conn):
    violations = conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    return [
        f"Foreign key violation: {tuple(row)}"
        for row in violations
    ]


def check_primary_keys(conn):
    errors = []

    entities = {
        "roles": "role_id",
        "requesters": "requester_id",
        "terms": "term_id",
        "categories": "category_id",
        "policy_documents": "policy_id",
        "knowledge_articles": "article_id",
        "tickets": "ticket_id",
        "messages": "message_id",
        "assignments": "assignment_id",
        "sla": "sla_id",
        "resolution_feedback": "feedback_id",
        "ticket_events": "event_id",
    }

    tables = get_tables(conn)

    for table, key in entities.items():
        if table not in tables:
            errors.append(f"Missing table: {table}")
            continue

        duplicate = conn.execute(f"""
            SELECT {key}, COUNT(*) AS total
            FROM {table}
            GROUP BY {key}
            HAVING COUNT(*) > 1
            LIMIT 1
        """).fetchone()

        if duplicate:
            errors.append(
                f"Duplicate primary key in {table}"
            )

    return errors


def check_ticket_statuses(conn):
    errors = []

    rows = conn.execute("""
        SELECT ticket_id, status
        FROM tickets
    """).fetchall()

    for row in rows:
        if row["status"] not in VALID_STATUSES:
            errors.append(
                f"Ticket {row['ticket_id']}: "
                f"invalid status {row['status']}"
            )

    return errors


def check_ticket_chronology(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            ticket_id,
            created_at,
            updated_at
        FROM tickets
    """).fetchall()

    for row in rows:
        try:
            created = datetime.strptime(
                row["created_at"], DATE_FORMAT
            )
            updated = datetime.strptime(
                row["updated_at"], DATE_FORMAT
            )

            if updated < created:
                errors.append(
                    f"Ticket {row['ticket_id']}: "
                    "updated before creation"
                )

        except (ValueError, TypeError):
            errors.append(
                f"Ticket {row['ticket_id']}: "
                "invalid timestamp"
            )

    return errors


def check_message_chronology(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            m.message_id,
            m.ticket_id,
            m.created_at AS message_time,
            t.created_at AS ticket_time
        FROM messages m
        JOIN tickets t
            ON m.ticket_id = t.ticket_id
    """).fetchall()

    for row in rows:
        try:
            message_time = datetime.strptime(
                row["message_time"], DATE_FORMAT
            )
            ticket_time = datetime.strptime(
                row["ticket_time"], DATE_FORMAT
            )

            if message_time < ticket_time:
                errors.append(
                    f"Message {row['message_id']}: "
                    "created before its ticket"
                )

        except (ValueError, TypeError):
            errors.append(
                f"Message {row['message_id']}: "
                "invalid timestamp"
            )

    return errors


def check_policy_dates(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            policy_id,
            effective_from,
            effective_to
        FROM policy_documents
    """).fetchall()

    for row in rows:
        try:
            start = datetime.strptime(
                row["effective_from"], "%Y-%m-%d"
            )

            if row["effective_to"]:
                end = datetime.strptime(
                    row["effective_to"], "%Y-%m-%d"
                )

                if end < start:
                    errors.append(
                        f"Policy {row['policy_id']}: "
                        "expiry before effective date"
                    )

        except (ValueError, TypeError):
            errors.append(
                f"Policy {row['policy_id']}: "
                "invalid effective date"
            )

    return errors


def check_sla(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            t.ticket_id,
            t.created_at,
            c.resolution_hours,
            s.response_deadline,
            s.resolution_deadline
        FROM tickets t
        JOIN categories c
            ON c.category_id = t.category_id
        LEFT JOIN sla s
            ON s.ticket_id = t.ticket_id
    """).fetchall()

    for row in rows:
        ticket_id = row["ticket_id"]

        if row["response_deadline"] is None:
            errors.append(
                f"Ticket {ticket_id}: missing SLA"
            )
            continue

        try:
            expected = calculate_sla_deadlines(
                row["created_at"],
                row["resolution_hours"]
            )

            if (
                row["response_deadline"]
                != expected["response_deadline"]
            ):
                errors.append(
                    f"Ticket {ticket_id}: "
                    "incorrect response deadline"
                )

            if (
                row["resolution_deadline"]
                != expected["resolution_deadline"]
            ):
                errors.append(
                    f"Ticket {ticket_id}: "
                    "incorrect resolution deadline"
                )

        except (ValueError, TypeError) as exc:
            errors.append(
                f"Ticket {ticket_id}: SLA error: {exc}"
            )

    return errors


def check_routing(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            t.ticket_id,
            t.status,
            c.support_team AS authorized_team,
            a.assigned_team
        FROM tickets t
        JOIN categories c
            ON c.category_id = t.category_id
        LEFT JOIN assignments a
            ON a.assignment_id = (
                SELECT MAX(a2.assignment_id)
                FROM assignments a2
                WHERE a2.ticket_id = t.ticket_id
            )
    """).fetchall()

    for row in rows:
        if row["assigned_team"] is None:
            if row["status"] != "Open":
                errors.append(
                    f"Ticket {row['ticket_id']}: "
                    "missing assignment"
                )

        elif (
            row["assigned_team"]
            != row["authorized_team"]
        ):
            errors.append(
                f"Ticket {row['ticket_id']}: "
                "unauthorized assignment"
            )

    return errors


def check_duplicate_codes(conn):
    errors = []

    fields = {
        "tickets": "ticket_number",
        "policy_documents": "policy_code",
        "knowledge_articles": "article_code",
    }

    for table, field in fields.items():
        duplicates = conn.execute(f"""
            SELECT {field}, COUNT(*) AS total
            FROM {table}
            WHERE {field} IS NOT NULL
            GROUP BY {field}
            HAVING COUNT(*) > 1
            LIMIT 1
        """).fetchone()

        if duplicates:
            errors.append(
                f"Duplicate {field} in {table}"
            )

    return errors


def check_lifecycle_events(conn):
    errors = []

    rows = conn.execute("""
        SELECT
            t.ticket_id,
            t.status,
            COUNT(e.event_id) AS event_count
        FROM tickets t
        LEFT JOIN ticket_events e
            ON e.ticket_id = t.ticket_id
        GROUP BY t.ticket_id
    """).fetchall()

    for row in rows:
        if row["event_count"] == 0:
            errors.append(
                f"Ticket {row['ticket_id']}: "
                "no lifecycle history"
            )

    return errors


def main():
    checks = [
        ("Record counts", check_counts),
        ("Foreign keys", check_foreign_keys),
        ("Primary keys", check_primary_keys),
        ("Ticket statuses", check_ticket_statuses),
        ("Ticket chronology", check_ticket_chronology),
        ("Message chronology", check_message_chronology),
        ("Policy effective dates", check_policy_dates),
        ("Business-hours SLA", check_sla),
        ("Authorized routing", check_routing),
        ("Duplicate identifiers", check_duplicate_codes),
        ("Lifecycle event presence", check_lifecycle_events),
    ]

    print("\nCampusResolve Dataset Validation")
    print("=" * 50)

    conn = connect()
    total_errors = 0

    try:
        for name, function in checks:
            try:
                errors = function(conn)
            except sqlite3.Error as exc:
                errors = [f"SQL error: {exc}"]

            if errors:
                print(f"[FAIL] {name}: {len(errors)} issue(s)")

                for error in errors[:5]:
                    print("   -", error)

                if len(errors) > 5:
                    print(
                        f"   ... and {len(errors) - 5} more"
                    )
            else:
                print(f"[PASS] {name}")

            total_errors += len(errors)

        print("=" * 50)
        print("Checks performed:", len(checks))
        print("Total validation issues:", total_errors)

        if total_errors == 0:
            print("RESULT: BASELINE VALIDATION PASSED")
        else:
            print("RESULT: BASELINE VALIDATION NEEDS REVIEW")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
