
from datetime import datetime
from zoneinfo import ZoneInfo

from database import get_connection


TIMEZONE = ZoneInfo("Asia/Kolkata")

FINAL_STATUSES = ("Resolved", "Closed")


def escalate_to_human(ticket_id, reason, conn=None):
    """
    Escalate a ticket to its authorized human support team.

    - Uses the ticket category's configured team.
    - Records the escalation in ticket history.
    - Prevents duplicate human assignments.
    - Does not modify resolved or closed tickets.
    """
    owns_connection = conn is None

    if owns_connection:
        conn = get_connection()

    try:
        ticket = conn.execute("""
            SELECT
                t.ticket_id,
                t.status,
                c.support_team,
                c.category_name
            FROM tickets t
            JOIN categories c
                ON t.category_id = c.category_id
            WHERE t.ticket_id = ?
        """, (ticket_id,)).fetchone()

        if ticket is None:
            return {
                "decision": "TICKET_NOT_FOUND",
                "ticket_id": ticket_id
            }

        if ticket["status"] in FINAL_STATUSES:
            return {
                "decision": "ALREADY_FINAL",
                "ticket_id": ticket_id
            }

        team = ticket["support_team"]

        if not team:
            return {
                "decision": "NO_AUTHORIZED_TEAM",
                "ticket_id": ticket_id
            }

        existing = conn.execute("""
            SELECT assignment_id
            FROM assignments
            WHERE ticket_id = ?
              AND assigned_team = ?
            LIMIT 1
        """, (ticket_id, team)).fetchone()

        now = datetime.now(TIMEZONE).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if existing is None:
            conn.execute("""
                INSERT INTO assignments (
                    ticket_id,
                    assigned_team,
                    assigned_at
                )
                VALUES (?, ?, ?)
            """, (
                ticket_id,
                team,
                now
            ))

        # Avoid repeating the same escalation event.
        existing_event = conn.execute("""
            SELECT event_id
            FROM ticket_events
            WHERE ticket_id = ?
              AND event_type = 'Human Escalation'
              AND event_description = ?
            LIMIT 1
        """, (
            ticket_id,
            f"Human review required: {reason}. "
            f"Assigned to {team}."
        )).fetchone()

        if existing_event is None:
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
                "Human Escalation",
                f"Human review required: {reason}. "
                f"Assigned to {team}.",
                now
            ))

        if ticket["status"] != "Escalated":
            conn.execute("""
                UPDATE tickets
                SET status = 'Escalated',
                    updated_at = ?
                WHERE ticket_id = ?
            """, (
                now,
                ticket_id
            ))

        if owns_connection:
            conn.commit()

        return {
            "decision": "HUMAN_ESCALATION",
            "ticket_id": ticket_id,
            "assigned_team": team,
            "reason": reason
        }

    finally:
        if owns_connection:
            conn.close()


def process_pending_escalations():
    """
    Find tickets already marked Escalated and
    ensure they have human review assignments.
    """
    conn = get_connection()

    try:
        tickets = conn.execute("""
            SELECT ticket_id
            FROM tickets
            WHERE status = 'Escalated'
            ORDER BY ticket_id
        """).fetchall()

        processed = 0

        for ticket in tickets:
            result = escalate_to_human(
                ticket["ticket_id"],
                "Automated escalation review",
                conn=conn
            )

            if result["decision"] == "HUMAN_ESCALATION":
                processed += 1

        conn.commit()

        return processed

    finally:
        conn.close()


if __name__ == "__main__":
    count = process_pending_escalations()

    print("CampusResolve Human Escalation")
    print("------------------------------")
    print("Escalated tickets checked:", count)
    print("Human support assignment check completed.")
