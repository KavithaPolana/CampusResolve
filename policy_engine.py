
import re
from datetime import datetime, timezone

from database import get_connection


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be",
    "can", "could", "do", "does", "for", "from",
    "have", "how", "i", "in", "is", "it", "me",
    "my", "of", "on", "or", "please", "the",
    "this", "to", "we", "what", "when", "where",
    "who", "why", "with", "you", "your",
    "help", "issue", "problem", "request",
    "student", "students", "faculty", "support",
    "team", "unable", "need", "not", "working"
}


# These are specific supported topics, not broad synonym groups.
# Each topic requires a meaningful phrase or combination.
SUPPORTED_TOPICS = {
    "portal_access": (
        "student portal",
        "portal password",
        "password reset",
        "reset password",
        "login issue",
        "login problem",
        "account recovery",
        "access student portal",
        "access the student portal",
        "student account"
    ),
    "scholarship": (
        "scholarship",
        "financial aid",
        "tuition assistance",
        "student funding"
    ),
    "registration": (
        "course registration",
        "registration deadline",
        "register for courses",
        "course enrollment",
        "enrollment deadline"
    ),
    "accessibility": (
        "accessibility",
        "accommodation",
        "assistive technology",
        "accessible learning"
    )
}


# Unsupported requests must not be answered using an
# unrelated general policy.
UNSUPPORTED_SOFTWARE_PHRASES = (
    "unsupported software",
    "special software",
    "unlisted software",
    "software application",
    "not listed in",
    "not covered by"
)


def timestamp_now():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def normalize_text(text):
    words = re.findall(
        r"[a-z0-9]+",
        (text or "").lower()
    )
    return " ".join(words)


def tokenize(text):
    return {
        word
        for word in re.findall(
            r"[a-z0-9]+",
            (text or "").lower()
        )
        if len(word) > 2 and word not in STOP_WORDS
    }


def identify_topics(text):
    normalized = normalize_text(text)
    topics = set()

    for topic, phrases in SUPPORTED_TOPICS.items():
        for phrase in phrases:
            if normalize_text(phrase) in normalized:
                topics.add(topic)
                break

    return topics


def relevance_score(question, article_title, policy_title):
    """
    Compatibility helper for existing tests.

    Only meaningful topic matches receive a score.
    A generic word such as 'access' is not enough.
    """
    question_topics = identify_topics(question)

    source_topics = identify_topics(
        article_title + " " + policy_title
    )

    return len(question_topics.intersection(source_topics))


def find_policy(ticket_id, conn, as_of=None):
    """
    Return SUPPORTED only when a current policy covers
    the specific question topic.

    Otherwise return ESCALATE for human review.
    """

    if as_of is None:
        as_of = datetime.now(
            timezone.utc
        ).date().isoformat()

    ticket = conn.execute("""
        SELECT
            t.ticket_id,
            t.subject,
            t.description,
            t.category_id,
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

    question = (
        ticket["subject"] + " "
        + ticket["description"]
    )

    normalized_question = normalize_text(question)

    # A known unsupported-software request is not
    # covered by a portal password-reset policy.
    if any(
        normalize_text(phrase) in normalized_question
        for phrase in UNSUPPORTED_SOFTWARE_PHRASES
    ):
        return {
            "decision": "ESCALATE",
            "reason": (
                "The request concerns software or services "
                "not confirmed by an approved policy. "
                "Human review is required."
            ),
            "ticket_id": ticket_id,
            "policy": None
        }

    question_topics = identify_topics(question)

    if not question_topics:
        return {
            "decision": "ESCALATE",
            "reason": (
                "No recognized, sufficiently specific "
                "policy topic was found. "
                "Human review is required."
            ),
            "ticket_id": ticket_id,
            "policy": None
        }

    articles = conn.execute("""
        SELECT
            k.article_id,
            k.article_code,
            k.title AS article_title,
            k.content AS article_content,
            p.policy_id,
            p.policy_code,
            p.title AS policy_title,
            p.version,
            p.content AS policy_content,
            p.effective_from,
            p.effective_to
        FROM knowledge_articles k
        JOIN policy_documents p
            ON k.policy_id = p.policy_id
        WHERE p.category_id = ?
          AND p.effective_from <= ?
          AND (
              p.effective_to IS NULL
              OR p.effective_to >= ?
          )
        ORDER BY p.version DESC, k.article_id
    """, (
        ticket["category_id"],
        as_of,
        as_of
    )).fetchall()

    best_article = None
    best_score = 0

    for article in articles:
        source_text = (
            article["article_title"] + " "
            + article["policy_title"] + " "
            + article["article_content"] + " "
            + article["policy_content"]
        )

        source_topics = identify_topics(source_text)

        matched_topics = (
            question_topics.intersection(source_topics)
        )

        score = len(matched_topics)

        if score > best_score:
            best_score = score
            best_article = article

    if best_article is None:
        return {
            "decision": "ESCALATE",
            "reason": (
                "No sufficiently relevant, currently "
                "effective policy was found. "
                "Human review is required."
            ),
            "ticket_id": ticket_id,
            "policy": None
        }

    return {
        "decision": "SUPPORTED",
        "reason": (
            "A currently effective policy matches "
            "the identified request topic."
        ),
        "ticket_id": ticket_id,
        "policy": dict(best_article),
        "relevance_score": best_score
    }


def process_ticket_policy(ticket_id, conn=None, as_of=None):
    """
    Record a policy-grounded response or escalate.

    Does not duplicate processing for an existing ticket.
    """

    own_connection = conn is None

    if own_connection:
        conn = get_connection()

    try:
        previous = conn.execute("""
            SELECT event_id
            FROM ticket_events
            WHERE ticket_id = ?
              AND event_type IN (
                  'Policy Answer Generated',
                  'Policy Escalation'
              )
            LIMIT 1
        """, (ticket_id,)).fetchone()

        if previous:
            return {
                "ticket_id": ticket_id,
                "decision": "ALREADY_PROCESSED"
            }

        result = find_policy(
            ticket_id,
            conn,
            as_of=as_of
        )

        now = timestamp_now()

        if result["decision"] == "ESCALATE":
            cursor = conn.execute("""
                UPDATE tickets
                SET status = 'Escalated',
                    updated_at = ?
                WHERE ticket_id = ?
                  AND status NOT IN ('Resolved', 'Closed')
            """, (now, ticket_id))

            if cursor.rowcount:
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
                    "Policy Escalation",
                    result["reason"],
                    now
                ))

        else:
            policy = result["policy"]

            answer = (
                policy["policy_content"]
                + "\n\nSource: "
                + (
                    policy["policy_code"]
                    or f"Policy {policy['policy_id']}"
                )
                + " | Version "
                + str(policy["version"])
                + " | Effective from "
                + policy["effective_from"]
                + " | Effective to "
                + (
                    policy["effective_to"]
                    or "No specified expiry"
                )
            )

            cursor = conn.execute("""
                INSERT INTO messages (
                    ticket_id,
                    sender_type,
                    message_text,
                    policy_id,
                    policy_version,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ticket_id,
                "Automated Support",
                answer,
                policy["policy_id"],
                policy["version"],
                now
            ))

            message_id = cursor.lastrowid

            conn.execute("""
                UPDATE messages
                SET message_number = ?
                WHERE message_id = ?
            """, (
                f"MSG-{ticket_id}-{message_id:03d}",
                message_id
            ))

            conn.execute("""
                INSERT INTO policy_citations (
                    message_id,
                    policy_id,
                    article_id,
                    cited_version,
                    cited_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                message_id,
                policy["policy_id"],
                policy["article_id"],
                policy["version"],
                now
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
                "Policy Answer Generated",
                "Response grounded in policy "
                + (
                    policy["policy_code"]
                    or str(policy["policy_id"])
                )
                + ", version "
                + str(policy["version"]),
                now
            ))

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


if __name__ == "__main__":
    print("CampusResolve Policy Engine")
    print("Specific-topic matching enabled.")
    print("Unsupported requests require human review.")
