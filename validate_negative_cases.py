
import csv
import sqlite3
from pathlib import Path

from sla_engine import calculate_sla_deadlines


ROOT = Path(__file__).resolve().parent

DATABASE = ROOT / "synthetic_campusresolve_negative.db"
GROUND_TRUTH = ROOT / "ground_truth.csv"
REPORT = ROOT / "negative_validation_report.csv"

SUPPORTED_TYPES = {
    "EXPIRED_POLICY",
    "UNAUTHORIZED_ROUTING",
    "UNSUPPORTED_ANSWER",
    "SLA_BUSINESS_HOURS_ERROR",
    "MISSED_ESCALATION",
}


def get_connection():
    conn = sqlite3.connect(
        f"file:{DATABASE.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row
    return conn


def expired_policy(conn, ticket_id):
    rows = conn.execute("""
        SELECT
            m.created_at,
            p.effective_from,
            p.effective_to
        FROM messages m
        JOIN policy_citations pc
            ON pc.message_id = m.message_id
        JOIN policy_documents p
            ON p.policy_id = pc.policy_id
        WHERE m.ticket_id = ?
    """, (ticket_id,)).fetchall()

    for row in rows:
        citation_date = row["created_at"][:10]

        if row["effective_from"] > citation_date:
            return True

        if (
            row["effective_to"] is not None
            and row["effective_to"] < citation_date
        ):
            return True

    return False


def unauthorized_routing(conn, ticket_id):
    row = conn.execute("""
        SELECT
            a.assigned_team,
            c.support_team
        FROM tickets t
        JOIN categories c
            ON c.category_id = t.category_id
        JOIN assignments a
            ON a.ticket_id = t.ticket_id
        WHERE t.ticket_id = ?
        ORDER BY a.assignment_id DESC
        LIMIT 1
    """, (ticket_id,)).fetchone()

    if row is None:
        return False

    return (
        row["assigned_team"] != row["support_team"]
    )


def unsupported_answer(conn, ticket_id):
    """
    Starter rule-based detector.

    The injected unsupported claim contains a
    guarantee not present in the approved policy.

    This is a targeted detector, not a general
    natural-language fact-checking system.
    """
    rows = conn.execute("""
        SELECT
            m.message_text,
            p.content AS policy_content
        FROM messages m
        JOIN policy_documents p
            ON p.policy_id = m.policy_id
        WHERE m.ticket_id = ?
          AND m.sender_type = 'Automated Support'
    """, (ticket_id,)).fetchall()

    for row in rows:
        answer = row["message_text"].lower()
        source = row["policy_content"].lower()

        unsupported_phrase = (
            "guaranteed approval within one hour"
        )

        if (
            unsupported_phrase in answer
            and unsupported_phrase not in source
        ):
            return True

    return False


def sla_business_hours_error(conn, ticket_id):
    row = conn.execute("""
        SELECT
            t.created_at,
            c.resolution_hours,
            s.response_deadline,
            s.resolution_deadline
        FROM tickets t
        JOIN categories c
            ON c.category_id = t.category_id
        JOIN sla s
            ON s.ticket_id = t.ticket_id
        WHERE t.ticket_id = ?
    """, (ticket_id,)).fetchone()

    if row is None:
        return False

    expected = calculate_sla_deadlines(
        row["created_at"],
        row["resolution_hours"]
    )

    return (
        row["response_deadline"]
        != expected["response_deadline"]
        or
        row["resolution_deadline"]
        != expected["resolution_deadline"]
    )


def missed_escalation(conn, ticket_id):
    ticket = conn.execute("""
        SELECT subject, description, status
        FROM tickets
        WHERE ticket_id = ?
    """, (ticket_id,)).fetchone()

    if ticket is None:
        return False

    text = (
        ticket["subject"] + " "
        + ticket["description"]
    ).lower()

    needs_human = (
        "existing approved policies do not cover"
        in text
        and "human review" in text
    )

    if not needs_human:
        return False

    event = conn.execute("""
        SELECT event_id
        FROM ticket_events
        WHERE ticket_id = ?
          AND event_type IN (
              'Policy Escalation',
              'Human Escalation',
              'SLA Escalation'
          )
        LIMIT 1
    """, (ticket_id,)).fetchone()

    return (
        ticket["status"] != "Escalated"
        and event is None
    )


DETECTORS = {
    "EXPIRED_POLICY": expired_policy,
    "UNAUTHORIZED_ROUTING": unauthorized_routing,
    "UNSUPPORTED_ANSWER": unsupported_answer,
    "SLA_BUSINESS_HOURS_ERROR": sla_business_hours_error,
    "MISSED_ESCALATION": missed_escalation,
}


def main():
    if not DATABASE.exists():
        print("ERROR: Negative database not found.")
        return

    if not GROUND_TRUTH.exists():
        print("ERROR: ground_truth.csv not found.")
        return

    with GROUND_TRUTH.open(
        newline="", encoding="utf-8"
    ) as file:
        cases = list(csv.DictReader(file))

    conn = get_connection()
    results = []

    try:
        for case in cases:
            issue_type = case["type"]
            ticket_id = int(case["ticket_id"])

            if issue_type not in SUPPORTED_TYPES:
                raise ValueError(
                    f"Unknown issue type: {issue_type}"
                )

            detected = DETECTORS[issue_type](
                conn, ticket_id
            )

            result = {
                "case_id": case["case_id"],
                "ticket_id": ticket_id,
                "issue_type": issue_type,
                "expected": case["expected"],
                "detected": int(detected),
                "result": (
                    "PASS" if detected else "FAIL"
                )
            }

            results.append(result)

    finally:
        conn.close()

    with REPORT.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "case_id",
                "ticket_id",
                "issue_type",
                "expected",
                "detected",
                "result"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nCampusResolve Negative Case Validation")
    print("-" * 45)

    for result in results:
        print(
            f"{result['case_id']} | "
            f"{result['issue_type']} | "
            f"{result['result']}"
        )

    passed = sum(
        result["result"] == "PASS"
        for result in results
    )

    total = len(results)

    print("-" * 45)
    print(f"Cases checked: {total}")
    print(f"Cases detected: {passed}")
    print(f"Cases missed: {total - passed}")
    print(f"Detection rate: {passed / total * 100:.1f}%"
          if total else "Detection rate: N/A")
    print("Report:", REPORT.name)


if __name__ == "__main__":
    main()
