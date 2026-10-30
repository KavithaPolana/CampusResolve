
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from database import get_connection


TIME_ZONE = ZoneInfo("Asia/Kolkata")

BUSINESS_START = time(9, 0)
BUSINESS_END = time(17, 0)

# Synthetic project rule: first response within
# two business hours for all categories.
RESPONSE_HOURS = 2

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_datetime(value):
    """
    Convert a datetime or database timestamp
    into a timezone-aware IST datetime.
    """
    if isinstance(value, str):
        value = datetime.strptime(value, DATE_FORMAT)

    if value.tzinfo is None:
        value = value.replace(tzinfo=TIME_ZONE)
    else:
        value = value.astimezone(TIME_ZONE)

    return value


def format_datetime(value):
    """
    Store timestamps in the same SQLite format
    used by the existing CampusResolve database.
    """
    return parse_datetime(value).strftime(DATE_FORMAT)


def next_business_time(value):
    """
    Return the same time if it is inside
    business hours, otherwise move forward
    to the next business opening.
    """
    current = parse_datetime(value)

    while True:
        if current.weekday() >= 5:
            current = (
                current + timedelta(days=1)
            ).replace(
                hour=9,
                minute=0,
                second=0,
                microsecond=0
            )
            continue

        if current.time() < BUSINESS_START:
            return current.replace(
                hour=9,
                minute=0,
                second=0,
                microsecond=0
            )

        if current.time() >= BUSINESS_END:
            current = (
                current + timedelta(days=1)
            ).replace(
                hour=9,
                minute=0,
                second=0,
                microsecond=0
            )
            continue

        return current


def add_business_hours(start, hours):
    """
    Add only Monday-Friday 09:00-17:00 hours.

    Example:
    Friday 16:00 + 8 business hours
    = Monday 16:00.
    """
    if hours < 0:
        raise ValueError(
            "Business hours cannot be negative."
        )

    current = next_business_time(start)
    remaining = timedelta(hours=hours)

    if remaining == timedelta(0):
        return current

    while remaining > timedelta(0):
        end_of_day = current.replace(
            hour=17,
            minute=0,
            second=0,
            microsecond=0
        )

        available = end_of_day - current

        if remaining <= available:
            return current + remaining

        remaining -= available

        current = next_business_time(
            end_of_day + timedelta(seconds=1)
        )

    return current


def calculate_sla_deadlines(
    created_at,
    resolution_hours
):
    """
    Calculate first-response and resolution
    deadlines from the ticket creation time.
    """
    if resolution_hours <= 0:
        raise ValueError(
            "Resolution hours must be positive."
        )

    created = parse_datetime(created_at)

    response_deadline = add_business_hours(
        created,
        RESPONSE_HOURS
    )

    resolution_deadline = add_business_hours(
        created,
        resolution_hours
    )

    return {
        "response_deadline": format_datetime(
            response_deadline
        ),
        "resolution_deadline": format_datetime(
            resolution_deadline
        )
    }


def create_ticket_sla(ticket_id, conn=None):
    """
    Create an SLA for an existing ticket.

    The resolution target comes from
    categories.resolution_hours.

    Safe to call more than once:
    an existing SLA will be preserved.
    """
    own_connection = conn is None

    if own_connection:
        conn = get_connection()

    try:
        ticket = conn.execute("""
            SELECT
                t.ticket_id,
                t.created_at,
                c.resolution_hours
            FROM tickets t
            JOIN categories c
                ON t.category_id = c.category_id
            WHERE t.ticket_id = ?
        """, (ticket_id,)).fetchone()

        if ticket is None:
            raise ValueError(
                f"Ticket {ticket_id} does not exist."
            )

        existing = conn.execute("""
            SELECT
                sla_id,
                response_deadline,
                resolution_deadline
            FROM sla
            WHERE ticket_id = ?
        """, (ticket_id,)).fetchone()

        if existing:
            return {
                "decision": "ALREADY_EXISTS",
                "ticket_id": ticket_id,
                "response_deadline": (
                    existing["response_deadline"]
                ),
                "resolution_deadline": (
                    existing["resolution_deadline"]
                )
            }

        deadlines = calculate_sla_deadlines(
            ticket["created_at"],
            ticket["resolution_hours"]
        )

        conn.execute("""
            INSERT INTO sla (
                ticket_id,
                response_deadline,
                resolution_deadline
            )
            VALUES (?, ?, ?)
        """, (
            ticket_id,
            deadlines["response_deadline"],
            deadlines["resolution_deadline"]
        ))

        conn.execute("""
            INSERT INTO ticket_events (
                ticket_id,
                event_type,
                event_description
            )
            VALUES (?, ?, ?)
        """, (
            ticket_id,
            "SLA Created",
            "Business-hours SLA created. "
            f"Response deadline: "
            f"{deadlines['response_deadline']}; "
            f"resolution deadline: "
            f"{deadlines['resolution_deadline']} "
            "(Asia/Kolkata)."
        ))

        if own_connection:
            conn.commit()

        return {
            "decision": "SLA_CREATED",
            "ticket_id": ticket_id,
            **deadlines
        }

    except Exception:
        if own_connection:
            conn.rollback()
        raise

    finally:
        if own_connection:
            conn.close()


def evaluate_sla(
    response_deadline,
    resolution_deadline,
    first_response_at=None,
    resolved_at=None,
    checked_at=None
):
    """
    Evaluate SLA deadlines.

    If a response/resolution occurred, compare
    its actual timestamp to the deadline.

    If it has not occurred, compare the current
    check time to the deadline.
    """
    now = parse_datetime(
        checked_at or datetime.now(TIME_ZONE)
    )

    response_due = parse_datetime(
        response_deadline
    )

    resolution_due = parse_datetime(
        resolution_deadline
    )

    response_time = (
        parse_datetime(first_response_at)
        if first_response_at
        else now
    )

    resolution_time = (
        parse_datetime(resolved_at)
        if resolved_at
        else now
    )

    return {
        "response_breached": (
            response_time > response_due
        ),
        "resolution_breached": (
            resolution_time > resolution_due
        ),
        "checked_at": format_datetime(now)
    }


if __name__ == "__main__":
    example = calculate_sla_deadlines(
        "2026-10-30 16:00:00",
        8
    )

    print("CampusResolve SLA Engine")
    print("Business hours: Mon-Fri, 09:00-17:00 IST")
    print("Example created: 2026-10-30 16:00:00")
    print("Response deadline:", example["response_deadline"])
    print("Resolution deadline:", example["resolution_deadline"])
