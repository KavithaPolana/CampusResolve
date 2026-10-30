
from datetime import datetime, timezone
from database import get_connection


def current_timestamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def route_ticket(ticket_id, conn=None):
    """
    Route a ticket using authorized category/team rules.

    Returns a dictionary containing the routing decision.
    """

    own_connection = conn is None

    if own_connection:
        conn = get_connection()

    try:
        ticket = conn.execute("""
            SELECT
                t.ticket_id,
                t.category_id,
                t.status,
                c.category_name
            FROM tickets t
            JOIN categories c
                ON t.category_id = c.category_id
            WHERE t.ticket_id = ?
        """, (ticket_id,)).fetchone()

        if ticket is None:
            raise ValueError(
                f"Ticket {ticket_id} does not exist."
            )

        # Prevent accidental duplicate routing.
        existing_assignment = conn.execute("""
            SELECT assignment_id, assigned_team
            FROM assignments
            WHERE ticket_id = ?
            ORDER BY assignment_id DESC
            LIMIT 1
        """, (ticket_id,)).fetchone()

        if existing_assignment is not None:
            return {
                "ticket_id": ticket_id,
                "status": ticket["status"],
                "assigned_team": existing_assignment[
                    "assigned_team"
                ],
                "decision": "ALREADY_ROUTED"
            }

        rule = conn.execute("""
            SELECT team_name
            FROM routing_rules
            WHERE category_id = ?
              AND is_authorized = 1
            ORDER BY rule_id
            LIMIT 1
        """, (ticket["category_id"],)).fetchone()

        timestamp = current_timestamp()

        if rule is None:
            # Exception path: no authorized team exists.
            conn.execute("""
                UPDATE tickets
                SET status = 'Escalated',
                    updated_at = ?
                WHERE ticket_id = ?
            """, (timestamp, ticket_id))

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
                "Routing Exception",
                "No authorized team found for category: "
                + ticket["category_name"],
                timestamp
            ))

            result = {
                "ticket_id": ticket_id,
                "status": "Escalated",
                "assigned_team": None,
                "decision": "NO_AUTHORIZED_TEAM"
            }

        else:
            team_name = rule["team_name"]

            conn.execute("""
                INSERT INTO assignments (
                    ticket_id,
                    assigned_team,
                    assigned_at
                )
                VALUES (?, ?, ?)
            """, (
                ticket_id,
                team_name,
                timestamp
            ))

            conn.execute("""
                UPDATE tickets
                SET status = 'Assigned',
                    updated_at = ?
                WHERE ticket_id = ?
            """, (timestamp, ticket_id))

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
                "Auto Assigned",
                "Ticket automatically routed to "
                + team_name
                + " using an authorized routing rule.",
                timestamp
            ))

            result = {
                "ticket_id": ticket_id,
                "status": "Assigned",
                "assigned_team": team_name,
                "decision": "AUTHORIZED_ROUTE"
            }

        if own_connection:
            conn.commit()

        return result

    except Exception:
        if own_connection:
            conn.rollback()
        raise

    finally:
        if own_connection:
            conn.close()
