
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "synthetic_campusresolve.db"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

VALID_STATUSES = {
    "Open",
    "Assigned",
    "In Progress",
    "Escalated",
    "Resolved",
    "Closed",
}


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
    return conn


def parse_date(value):
    if not value:
        return None

    return datetime.strptime(value, DATE_FORMAT)


def validate(conn):
    errors = []
    warnings = []
    status_counts = Counter()

    tickets = conn.execute("""
        SELECT
            t.ticket_id,
            t.status,
            t.created_at,
            t.updated_at,
            s.first_response_at,
            s.resolved_at,
            (
                SELECT COUNT(*)
                FROM assignments a
                WHERE a.ticket_id = t.ticket_id
            ) AS assignment_count,
            (
                SELECT COUNT(*)
                FROM resolution_feedback f
                WHERE f.ticket_id = t.ticket_id
            ) AS resolution_count,
            (
                SELECT COUNT(*)
                FROM ticket_events e
                WHERE e.ticket_id = t.ticket_id
            ) AS event_count,
            (
                SELECT COUNT(*)
                FROM ticket_events e
                WHERE e.ticket_id = t.ticket_id
                  AND LOWER(e.event_type)
                      LIKE '%escalat%'
            ) AS escalation_count
        FROM tickets t
        LEFT JOIN sla s
            ON s.ticket_id = t.ticket_id
        ORDER BY t.ticket_id
    """).fetchall()

    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        status = ticket["status"]

        status_counts[status] += 1

        if status not in VALID_STATUSES:
            errors.append(
                f"Ticket {ticket_id}: invalid status"
            )

        if (
            status != "Open"
            and ticket["assignment_count"] == 0
        ):
            errors.append(
                f"Ticket {ticket_id}: "
                "active ticket has no assignment"
            )

        if ticket["event_count"] == 0:
            errors.append(
                f"Ticket {ticket_id}: "
                "missing event history"
            )

        if (
            status in {"Resolved", "Closed"}
            and ticket["resolution_count"] == 0
        ):
            errors.append(
                f"Ticket {ticket_id}: "
                "resolved ticket has no resolution record"
            )

        if (
            status not in {"Resolved", "Closed"}
            and ticket["resolution_count"] > 0
        ):
            warnings.append(
                f"Ticket {ticket_id}: "
                "resolution record exists but "
                "ticket is not resolved"
            )

        if (
            status == "Escalated"
            and ticket["escalation_count"] == 0
        ):
            errors.append(
                f"Ticket {ticket_id}: "
                "escalated without escalation event"
            )

        if (
            status in {"Resolved", "Closed"}
            and ticket["resolved_at"] is None
        ):
            errors.append(
                f"Ticket {ticket_id}: "
                "resolved status has no SLA resolution time"
            )

        try:
            created = parse_date(
                ticket["created_at"]
            )
            updated = parse_date(
                ticket["updated_at"]
            )
            first_response = parse_date(
                ticket["first_response_at"]
            )
            resolved = parse_date(
                ticket["resolved_at"]
            )

            if updated and updated < created:
                errors.append(
                    f"Ticket {ticket_id}: "
                    "updated before creation"
                )

            if (
                first_response
                and first_response < created
            ):
                errors.append(
                    f"Ticket {ticket_id}: "
                    "response before creation"
                )

            if resolved and resolved < created:
                errors.append(
                    f"Ticket {ticket_id}: "
                    "resolution before creation"
                )

            if (
                first_response
                and resolved
                and resolved < first_response
            ):
                errors.append(
                    f"Ticket {ticket_id}: "
                    "resolved before first response"
                )

        except (ValueError, TypeError):
            errors.append(
                f"Ticket {ticket_id}: "
                "invalid lifecycle timestamp"
            )

    return tickets, status_counts, errors, warnings


def main():
    print()
    print("CampusResolve Lifecycle Validation")
    print("=" * 48)

    conn = connect()

    try:
        tickets, counts, errors, warnings = (
            validate(conn)
        )
    finally:
        conn.close()

    print("Tickets checked:", len(tickets))
    print()
    print("Status Distribution")
    print("-" * 48)

    for status in [
        "Open",
        "Assigned",
        "In Progress",
        "Escalated",
        "Resolved",
        "Closed",
    ]:
        print(
            f"{status}: {counts[status]}"
        )

    print()
    print("Lifecycle errors:", len(errors))
    print("Lifecycle warnings:", len(warnings))

    if errors:
        print()
        print("First errors:")

        for error in errors[:10]:
            print("-", error)

    if warnings:
        print()
        print("First warnings:")

        for warning in warnings[:10]:
            print("-", warning)

    print()
    print("=" * 48)

    if errors:
        print("RESULT: LIFECYCLE VALIDATION FAILED")
        sys.exit(1)

    print("RESULT: LIFECYCLE CONSISTENCY PASSED")
    print(
        "Note: Historical status-transition "
        "sequences were not independently verified."
    )


if __name__ == "__main__":
    main()
