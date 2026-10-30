
import csv
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE_DB = ROOT / "synthetic_campusresolve.db"
NEGATIVE_DB = ROOT / "synthetic_campusresolve_negative.db"
GROUND_TRUTH = ROOT / "ground_truth.csv"

CASES = [
    {
        "case_id": "NEG-001",
        "ticket_id": 10,
        "type": "EXPIRED_POLICY",
        "expected": "REJECT_CITATION_AND_ESCALATE",
        "description": "An automated response cites a policy that expired before the response."
    },
    {
        "case_id": "NEG-002",
        "ticket_id": 11,
        "type": "UNAUTHORIZED_ROUTING",
        "expected": "REJECT_ASSIGNMENT_AND_REROUTE",
        "description": "A ticket is assigned to a team not authorized for its category."
    },
    {
        "case_id": "NEG-003",
        "ticket_id": 12,
        "type": "UNSUPPORTED_ANSWER",
        "expected": "REJECT_ANSWER_AND_ESCALATE",
        "description": "An automated response makes a claim unsupported by the cited policy."
    },
    {
        "case_id": "NEG-004",
        "ticket_id": 13,
        "type": "SLA_BUSINESS_HOURS_ERROR",
        "expected": "RECALCULATE_BUSINESS_HOURS_SLA",
        "description": "A resolution deadline is calculated using calendar hours instead of business hours."
    },
    {
        "case_id": "NEG-005",
        "ticket_id": 14,
        "type": "MISSED_ESCALATION",
        "expected": "ESCALATE_TO_HUMAN",
        "description": "An explicitly unsupported request remains assigned without escalation."
    }
]


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_ticket(conn, ticket_id):
    ticket = conn.execute(
        "SELECT * FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    ).fetchone()

    if ticket is None:
        raise RuntimeError(f"Ticket {ticket_id} is missing.")

    return ticket


def inject_expired_policy(conn, ticket_id):
    ticket = get_ticket(conn, ticket_id)

    message = conn.execute("""
        SELECT m.message_id, m.created_at
        FROM messages m
        WHERE m.ticket_id = ?
          AND m.policy_id IS NOT NULL
        ORDER BY m.message_id
        LIMIT 1
    """, (ticket_id,)).fetchone()

    if message is None:
        raise RuntimeError("No cited message found for expired policy case.")

    # Choose a policy/article in the correct category that is
    # not currently cited by any other message.
    candidate = conn.execute("""
        SELECT
            p.policy_id,
            p.policy_code,
            p.version,
            p.content,
            k.article_id
        FROM policy_documents p
        JOIN knowledge_articles k
            ON k.policy_id = p.policy_id
        WHERE p.category_id = ?
          AND NOT EXISTS (
              SELECT 1
              FROM policy_citations pc
              WHERE pc.policy_id = p.policy_id
          )
        ORDER BY p.policy_id DESC
        LIMIT 1
    """, (ticket["category_id"],)).fetchone()

    if candidate is None:
        raise RuntimeError("No unused policy available for expired policy case.")

    cited_date = datetime.strptime(
        message["created_at"], "%Y-%m-%d %H:%M:%S"
    )

    expired_on = (
        cited_date - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    conn.execute("""
        UPDATE policy_documents
        SET effective_from = '2026-01-01',
            effective_to = ?
        WHERE policy_id = ?
    """, (expired_on, candidate["policy_id"]))

    conn.execute("""
        UPDATE messages
        SET policy_id = ?,
            policy_version = ?,
            message_text = ?
        WHERE message_id = ?
    """, (
        candidate["policy_id"],
        candidate["version"],
        candidate["content"]
        + "\nSource: "
        + candidate["policy_code"]
        + ", version "
        + str(candidate["version"]),
        message["message_id"]
    ))

    conn.execute("""
        UPDATE policy_citations
        SET policy_id = ?,
            article_id = ?,
            cited_version = ?
        WHERE message_id = ?
    """, (
        candidate["policy_id"],
        candidate["article_id"],
        candidate["version"],
        message["message_id"]
    ))


def inject_unauthorized_routing(conn, ticket_id):
    ticket = get_ticket(conn, ticket_id)

    correct_team = conn.execute("""
        SELECT support_team
        FROM categories
        WHERE category_id = ?
    """, (ticket["category_id"],)).fetchone()["support_team"]

    wrong_team = conn.execute("""
        SELECT support_team
        FROM categories
        WHERE support_team != ?
        ORDER BY category_id
        LIMIT 1
    """, (correct_team,)).fetchone()

    if wrong_team is None:
        raise RuntimeError("No alternative team available.")

    conn.execute("""
        UPDATE assignments
        SET assigned_team = ?
        WHERE assignment_id = (
            SELECT assignment_id
            FROM assignments
            WHERE ticket_id = ?
            ORDER BY assignment_id DESC
            LIMIT 1
        )
    """, (wrong_team["support_team"], ticket_id))


def inject_unsupported_answer(conn, ticket_id):
    message = conn.execute("""
        SELECT message_id, message_text
        FROM messages
        WHERE ticket_id = ?
          AND sender_type = 'Automated Support'
          AND policy_id IS NOT NULL
        ORDER BY message_id
        LIMIT 1
    """, (ticket_id,)).fetchone()

    if message is None:
        raise RuntimeError("No automated answer found.")

    unsupported_claim = (
        "\n\nAdditional claim: All requests in this category "
        "are guaranteed approval within one hour."
    )

    conn.execute("""
        UPDATE messages
        SET message_text = ?
        WHERE message_id = ?
    """, (
        message["message_text"] + unsupported_claim,
        message["message_id"]
    ))


def inject_sla_error(conn, ticket_id):
    ticket = get_ticket(conn, ticket_id)

    created = datetime.strptime(
        ticket["created_at"], "%Y-%m-%d %H:%M:%S"
    )

    category = conn.execute("""
        SELECT resolution_hours
        FROM categories
        WHERE category_id = ?
    """, (ticket["category_id"],)).fetchone()

    # Deliberately incorrect: adds continuous calendar hours.
    wrong_deadline = (
        created + timedelta(hours=category["resolution_hours"])
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE sla
        SET resolution_deadline = ?
        WHERE ticket_id = ?
    """, (wrong_deadline, ticket_id))


def inject_missed_escalation(conn, ticket_id):
    # This text explicitly states that approved guidance
    # cannot cover the request, so human review is required.
    conn.execute("""
        UPDATE tickets
        SET subject = ?,
            description = ?,
            status = 'Assigned'
        WHERE ticket_id = ?
    """, (
        "Unlisted exception requiring human review",
        "This is an unusual exception. Existing approved "
        "policies do not cover my circumstances. "
        "Please arrange human review.",
        ticket_id
    ))

    # The deliberately faulty record has no escalation event.
    conn.execute("""
        DELETE FROM ticket_events
        WHERE ticket_id = ?
          AND event_type IN (
              'Policy Escalation',
              'Human Escalation',
              'SLA Escalation'
          )
    """, (ticket_id,))


def main():
    if not SOURCE_DB.exists():
        print("ERROR: synthetic_campusresolve.db not found.")
        print("Run python generate_data.py first.")
        return

    if NEGATIVE_DB.exists() or GROUND_TRUTH.exists():
        print("Negative dataset or ground truth already exists.")
        print("No files were overwritten.")
        return

    shutil.copy2(SOURCE_DB, NEGATIVE_DB)

    conn = connect(NEGATIVE_DB)

    try:
        conn.execute("BEGIN")

        inject_expired_policy(conn, 10)
        inject_unauthorized_routing(conn, 11)
        inject_unsupported_answer(conn, 12)
        inject_sla_error(conn, 13)
        inject_missed_escalation(conn, 14)

        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign key violations: {len(violations)}"
            )

        expected_counts = {
            "tickets": 5000,
            "knowledge_articles": 200,
            "messages": 20000
        }

        for table, expected in expected_counts.items():
            actual = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            if actual != expected:
                raise RuntimeError(
                    f"{table}: expected {expected}, got {actual}"
                )

        conn.commit()

        with GROUND_TRUTH.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "case_id",
                    "ticket_id",
                    "ticket_number",
                    "type",
                    "expected",
                    "description"
                ]
            )

            writer.writeheader()

            for case in CASES:
                ticket = get_ticket(
                    conn, case["ticket_id"]
                )

                writer.writerow({
                    **case,
                    "ticket_number": ticket["ticket_number"]
                })

        print("CampusResolve negative dataset generated!")
        print("Negative database:", NEGATIVE_DB.name)
        print("Ground truth:", GROUND_TRUTH.name)
        print("Negative scenarios:", len(CASES))
        print("Tickets:", expected_counts["tickets"])
        print("Knowledge articles:", expected_counts["knowledge_articles"])
        print("Messages:", expected_counts["messages"])
        print("Foreign key violations: 0")

        for case in CASES:
            print(
                case["case_id"],
                "|",
                case["type"],
                "| Ticket",
                case["ticket_id"]
            )

    except Exception:
        conn.rollback()
        conn.close()
        NEGATIVE_DB.unlink(missing_ok=True)
        raise

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
