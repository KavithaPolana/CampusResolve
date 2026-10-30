
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from database import get_connection


TIMEZONE = ZoneInfo("Asia/Kolkata")

FINAL_STATUSES = ("Resolved", "Closed")


def current_time():
    """Return the current local time for SLA checks."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)


def parse_datetime(value):
    """Convert a database timestamp into a datetime."""
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    parsed = datetime.fromisoformat(str(value))

    if parsed.tzinfo is not None:
        return parsed.astimezone(TIMEZONE).replace(tzinfo=None)

    return parsed


def check_sla_breaches(conn=None, now=None):
    """
    Check active tickets for SLA breaches.

    A ticket is escalated when:
    - its response deadline passed without a response, or
    - its resolution deadline passed without resolution.

    Returns a summary of the checks.
    """
    owns_connection = conn is None

    if owns_connection:
        conn = get_connection()

    check_time = parse_datetime(now) if now else current_time()
    check_timestamp = check_time.strftime("%Y-%m-%d %H:%M:%S")

    summary = {
        "checked": 0,
        "response_breaches": 0,
        "resolution_breaches": 0,
        "tickets_escalated": 0
    }

    try:
        tickets = conn.execute("""
            SELECT
                t.ticket_id,
                t.status,
                s.response_deadline,
                s.resolution_deadline,
                s.first_response_at,
                s.resolved_at
            FROM tickets t
            JOIN sla s
                ON t.ticket_id = s.ticket_id
            WHERE t.status NOT IN ('Resolved', 'Closed')
            ORDER BY t.ticket_id
        """).fetchall()

        for ticket in tickets:
            summary["checked"] += 1

            ticket_id = ticket["ticket_id"]

            response_deadline = parse_datetime(
                ticket["response_deadline"]
            )

            resolution_deadline = parse_datetime(
                ticket["resolution_deadline"]
            )

            first_response = parse_datetime(
                ticket["first_response_at"]
            )

            resolved_at = parse_datetime(
                ticket["resolved_at"]
            )

            response_breached = (
                response_deadline is not None
                and check_time > response_deadline
                and (
                    first_response is None
                    or first_response > response_deadline
                )
            )

            resolution_breached = (
                resolution_deadline is not None
                and check_time > resolution_deadline
                and (
                    resolved_at is None
                    or resolved_at > resolution_deadline
                )
            )

            new_breach_found = False

            if response_breached:
                existing = conn.execute("""
                    SELECT 1
                    FROM ticket_events
                    WHERE ticket_id = ?
                      AND event_type = 'SLA Response Breach'
                    LIMIT 1
                """, (ticket_id,)).fetchone()

                if existing is None:
                    conn.execute("""
                        INSERT INTO ticket_events (
                            ticket_id,
                            event_type,
                            event_description,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        ticket_id,
                        "SLA Response Breach",
                        (
                            "First-response SLA deadline missed. "
                            f"Deadline: {ticket['response_deadline']}."
                        ),
                        check_timestamp
                    ))

                    summary["response_breaches"] += 1
                    new_breach_found = True

            if resolution_breached:
                existing = conn.execute("""
                    SELECT 1
                    FROM ticket_events
                    WHERE ticket_id = ?
                      AND event_type = 'SLA Resolution Breach'
                    LIMIT 1
                """, (ticket_id,)).fetchone()

                if existing is None:
                    conn.execute("""
                        INSERT INTO ticket_events (
                            ticket_id,
                            event_type,
                            event_description,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        ticket_id,
                        "SLA Resolution Breach",
                        (
                            "Resolution SLA deadline missed. "
                            f"Deadline: {ticket['resolution_deadline']}."
                        ),
                        check_timestamp
                    ))

                    summary["resolution_breaches"] += 1
                    new_breach_found = True

            if new_breach_found and ticket["status"] != "Escalated":
                conn.execute("""
                    UPDATE tickets
                    SET status = 'Escalated',
                        updated_at = ?
                    WHERE ticket_id = ?
                """, (
                    check_timestamp,
                    ticket_id
                ))

                conn.execute("""
                    INSERT INTO ticket_events (
                        ticket_id,
                        event_type,
                        event_description,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    ticket_id,
                    "SLA Auto Escalation",
                    (
                        "Ticket automatically escalated "
                        "because an SLA deadline was missed. "
                        "Human support review is required."
                    ),
                    check_timestamp
                ))

                summary["tickets_escalated"] += 1

        conn.commit()
        return summary

    finally:
        if owns_connection:
            conn.close()


if __name__ == "__main__":
    result = check_sla_breaches()

    print("\nCampusResolve SLA Monitoring")
    print("----------------------------")
    print("Tickets checked:", result["checked"])
    print("New response breaches:", result["response_breaches"])
    print("New resolution breaches:", result["resolution_breaches"])
    print("Tickets escalated:", result["tickets_escalated"])
