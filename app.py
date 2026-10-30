
import sqlite3
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort
)

from database import get_connection, create_database
from routing_engine import route_ticket
from policy_engine import process_ticket_policy
from sla_engine import create_ticket_sla


app = Flask(__name__)
app.secret_key = "campusresolve-local-development-key"

BASE_DIR = Path(__file__).resolve().parent
SYNTHETIC_DB = BASE_DIR / "synthetic_campusresolve.db"


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def open_synthetic_connection():
    """
    Open the 5,000-ticket database in read-only mode.
    This protects the generated challenge dataset.
    """
    if not SYNTHETIC_DB.exists():
        abort(
            503,
            description=(
                "Synthetic dataset not found. "
                "Run python generate_data.py first."
            )
        )

    conn = sqlite3.connect(
        f"file:{SYNTHETIC_DB.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row
    return conn


def open_ticket_connection(source):
    """
    Synthetic = generated 5,000 tickets.
    Live = tickets created through the website.
    """
    if source == "synthetic":
        return open_synthetic_connection()

    if source == "live":
        return get_connection()

    abort(400, description="Invalid ticket source.")


def public_ticket_number(row):
    if row["ticket_number"]:
        return row["ticket_number"]

    return f"TKT-2026-{row['ticket_id']:06d}"


def get_dashboard_stats(conn):
    stats = {
        "total": 0,
        "open": 0,
        "assigned": 0,
        "in_progress": 0,
        "resolved": 0,
        "escalated": 0,
        "closed": 0
    }

    rows = conn.execute("""
        SELECT status, COUNT(*) AS count
        FROM tickets
        GROUP BY status
    """).fetchall()

    for row in rows:
        count = row["count"]
        stats["total"] += count

        key = row["status"].lower().replace(" ", "_")

        if key in stats:
            stats[key] = count

    return stats


def get_recent_tickets(conn):
    rows = conn.execute("""
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.subject,
            c.category_name,
            t.status
        FROM tickets t
        JOIN categories c
            ON t.category_id = c.category_id
        ORDER BY t.created_at DESC, t.ticket_id DESC
        LIMIT 10
    """).fetchall()

    return [
        {
            "id": public_ticket_number(row),
            "ticket_id": row["ticket_id"],
            "subject": row["subject"],
            "category": row["category_name"],
            "status": row["status"]
        }
        for row in rows
    ]


def get_category_stats(conn):
    rows = conn.execute("""
        SELECT
            c.category_name,
            COUNT(t.ticket_id) AS ticket_count
        FROM categories c
        LEFT JOIN tickets t
            ON c.category_id = t.category_id
        GROUP BY c.category_id, c.category_name
        ORDER BY c.category_name
    """).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
def dashboard():
    live_conn = get_connection()

    try:
        live_stats = get_dashboard_stats(live_conn)
        recent_tickets = get_recent_tickets(live_conn)
    finally:
        live_conn.close()

    synthetic_available = SYNTHETIC_DB.exists()

    if synthetic_available:
        synthetic_conn = open_synthetic_connection()

        try:
            stats = get_dashboard_stats(synthetic_conn)
            category_stats = get_category_stats(synthetic_conn)
        finally:
            synthetic_conn.close()
    else:
        stats = live_stats
        category_stats = []

    return render_template(
        "index.html",
        stats=stats,
        live_stats=live_stats,
        recent_tickets=recent_tickets,
        category_stats=category_stats,
        synthetic_available=synthetic_available
    )


# --------------------------------------------------
# CREATE LIVE TICKET
# --------------------------------------------------

@app.route("/create-ticket", methods=["GET", "POST"])
def create_ticket():
    conn = get_connection()
    error = None

    try:
        if request.method == "POST":

            try:
                requester_id = int(
                    request.form.get("requester_id", "")
                )

                category_id = int(
                    request.form.get("category_id", "")
                )

            except (TypeError, ValueError):
                error = (
                    "Please select a valid requester "
                    "and support category."
                )

            if error is None:

                subject = request.form.get(
                    "subject", ""
                ).strip()

                description = request.form.get(
                    "description", ""
                ).strip()

                requester = conn.execute("""
                    SELECT r.requester_id
                    FROM requesters r
                    JOIN roles ro
                        ON r.role_id = ro.role_id
                    WHERE r.requester_id = ?
                      AND ro.role_name IN (
                          'Student',
                          'Faculty'
                      )
                """, (requester_id,)).fetchone()

                category = conn.execute("""
                    SELECT category_id
                    FROM categories
                    WHERE category_id = ?
                """, (category_id,)).fetchone()

                if requester is None:
                    error = "Please select a valid requester."

                elif category is None:
                    error = "Please select a valid category."

                elif not subject:
                    error = "Subject is required."

                elif not description:
                    error = "Description is required."

                elif len(subject) > 150:
                    error = (
                        "Subject must contain "
                        "150 characters or fewer."
                    )

                else:
                    try:
                        with conn:

                            # Create ticket
                            cursor = conn.execute("""
                                INSERT INTO tickets (
                                    requester_id,
                                    category_id,
                                    subject,
                                    description,
                                    status
                                )
                                VALUES (?, ?, ?, ?, 'Open')
                            """, (
                                requester_id,
                                category_id,
                                subject,
                                description
                            ))

                            ticket_id = cursor.lastrowid

                            ticket_number = (
                                f"TKT-2026-{ticket_id:06d}"
                            )

                            conn.execute("""
                                UPDATE tickets
                                SET ticket_number = ?
                                WHERE ticket_id = ?
                            """, (
                                ticket_number,
                                ticket_id
                            ))

                            # Record creation event
                            conn.execute("""
                                INSERT INTO ticket_events (
                                    ticket_id,
                                    event_type,
                                    event_description
                                )
                                VALUES (?, ?, ?)
                            """, (
                                ticket_id,
                                "Created",
                                "Ticket submitted by requester."
                            ))

                            # Automatic routing
                            routing_result = route_ticket(
                                ticket_id,
                                conn=conn
                            )

                            # Business-hours SLA
                            create_ticket_sla(
                                ticket_id,
                                conn=conn
                            )

                            # Policy-grounded answer
                            if (
                                routing_result["decision"]
                                == "AUTHORIZED_ROUTE"
                            ):
                                policy_result = (
                                    process_ticket_policy(
                                        ticket_id,
                                        conn=conn
                                    )
                                )
                            else:
                                policy_result = {
                                    "decision": "NOT_PROCESSED"
                                }

                        if (
                            policy_result["decision"]
                            == "SUPPORTED"
                        ):
                            flash(
                                "Ticket created successfully! "
                                "Automatic routing, SLA and "
                                "policy response are complete.",
                                "success"
                            )

                        elif (
                            policy_result["decision"]
                            == "ESCALATE"
                        ):
                            flash(
                                "Ticket created successfully. "
                                "Human support is required.",
                                "error"
                            )

                        else:
                            flash(
                                "Ticket created successfully. "
                                "The request requires human review.",
                                "error"
                            )

                        return redirect(
                            url_for(
                                "ticket_details",
                                ticket_id=ticket_id,
                                source="live"
                            )
                        )

                    except Exception:
                        app.logger.exception(
                            "Automatic ticket processing failed"
                        )

                        error = (
                            "Unable to create the ticket. "
                            "Please check the terminal."
                        )

        requesters = conn.execute("""
            SELECT
                r.requester_id,
                r.name,
                ro.role_name
            FROM requesters r
            JOIN roles ro
                ON r.role_id = ro.role_id
            WHERE ro.role_name IN (
                'Student',
                'Faculty'
            )
            ORDER BY r.name
        """).fetchall()

        categories = conn.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """).fetchall()

    finally:
        conn.close()

    return render_template(
        "create_ticket.html",
        requesters=requesters,
        categories=categories,
        success=False,
        error=error,
        ticket_number=None,
        assigned_team=None
    )


# --------------------------------------------------
# ALL TICKETS — 5,000 SYNTHETIC + LIVE
# --------------------------------------------------

@app.route("/tickets")
def all_tickets():

    source = request.args.get(
        "source", "synthetic"
    )

    if source not in ("synthetic", "live"):
        abort(400)

    page = request.args.get(
        "page", 1, type=int
    )

    page = max(page, 1)
    per_page = 50

    search = request.args.get(
        "q", ""
    ).strip()[:100]

    status = request.args.get(
        "status", ""
    ).strip()

    allowed_statuses = {
        "",
        "Open",
        "Assigned",
        "In Progress",
        "Resolved",
        "Escalated",
        "Closed"
    }

    if status not in allowed_statuses:
        abort(400)

    conn = open_ticket_connection(source)

    try:
        conditions = []
        parameters = []

        if search:
            conditions.append("""
                (
                    t.subject LIKE ?
                    OR t.ticket_number LIKE ?
                )
            """)

            parameters.extend([
                f"%{search}%",
                f"%{search}%"
            ])

        if status:
            conditions.append(
                "t.status = ?"
            )
            parameters.append(status)

        where_sql = ""

        if conditions:
            where_sql = (
                "WHERE " + " AND ".join(conditions)
            )

        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM tickets t
            {where_sql}
            """,
            parameters
        ).fetchone()[0]

        total_pages = max(
            1,
            (total + per_page - 1) // per_page
        )

        page = min(page, total_pages)

        offset = (page - 1) * per_page

        rows = conn.execute(
            f"""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.subject,
                t.status,
                r.name AS requester_name,
                c.category_name,

                (
                    SELECT a.assigned_team
                    FROM assignments a
                    WHERE a.ticket_id = t.ticket_id
                    ORDER BY a.assignment_id DESC
                    LIMIT 1
                ) AS assigned_team

            FROM tickets t

            JOIN requesters r
                ON t.requester_id = r.requester_id

            JOIN categories c
                ON t.category_id = c.category_id

            {where_sql}

            ORDER BY t.ticket_id DESC

            LIMIT ? OFFSET ?
            """,
            parameters + [per_page, offset]
        ).fetchall()

        tickets = []

        for row in rows:
            ticket = dict(row)

            ticket["ticket_number"] = (
                public_ticket_number(row)
            )

            tickets.append(ticket)

    finally:
        conn.close()

    return render_template(
        "all_tickets.html",
        tickets=tickets,
        source=source,
        total=total,
        page=page,
        total_pages=total_pages,
        search=search,
        status=status
    )


# --------------------------------------------------
# TICKET DETAILS — SYNTHETIC OR LIVE
# --------------------------------------------------

@app.route("/tickets/<int:ticket_id>")
def ticket_details(ticket_id):

    source = request.args.get(
        "source", "synthetic"
    )

    conn = open_ticket_connection(source)

    try:
        row = conn.execute("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.subject,
                t.description,
                t.status,
                t.created_at,
                t.updated_at,

                r.name AS requester_name,
                ro.role_name,
                c.category_name,

                (
                    SELECT a.assigned_team
                    FROM assignments a
                    WHERE a.ticket_id = t.ticket_id
                    ORDER BY a.assignment_id DESC
                    LIMIT 1
                ) AS assigned_team

            FROM tickets t

            JOIN requesters r
                ON t.requester_id = r.requester_id

            JOIN roles ro
                ON r.role_id = ro.role_id

            JOIN categories c
                ON t.category_id = c.category_id

            WHERE t.ticket_id = ?
        """, (ticket_id,)).fetchone()

        if row is None:
            abort(404)

        ticket = dict(row)

        ticket["ticket_number"] = (
            public_ticket_number(row)
        )

        events = conn.execute("""
            SELECT
                event_type,
                event_description,
                created_at
            FROM ticket_events
            WHERE ticket_id = ?
            ORDER BY created_at, event_id
        """, (ticket_id,)).fetchall()

        messages = conn.execute("""
            SELECT
                m.sender_type,
                m.message_text,
                m.created_at,
                m.policy_version,

                p.policy_code,
                p.title AS policy_title,
                p.effective_from,
                p.effective_to

            FROM messages m

            LEFT JOIN policy_documents p
                ON m.policy_id = p.policy_id

            WHERE m.ticket_id = ?

            ORDER BY
                m.created_at,
                m.message_id
        """, (ticket_id,)).fetchall()

        sla = conn.execute("""
            SELECT
                response_deadline,
                resolution_deadline,
                first_response_at,
                resolved_at
            FROM sla
            WHERE ticket_id = ?
        """, (ticket_id,)).fetchone()

    finally:
        conn.close()

    return render_template(
        "ticket_details.html",
        ticket=ticket,
        events=events,
        messages=messages,
        sla=sla,
        source=source
    )


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    create_database()

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True
    )
