
from datetime import date
from database import get_connection, create_database


POLICIES = [
    {
        "category": "Financial Aid",
        "title": "Scholarship Application Support",
        "version": 1,
        "effective_from": "2025-01-01",
        "effective_to": "2025-12-31",
        "content": (
            "For the 2025 academic year, students may request "
            "scholarship application assistance through the "
            "Financial Aid Team."
        ),
        "article_title": "How to request scholarship support"
    },
    {
        "category": "Financial Aid",
        "title": "Scholarship Application Support",
        "version": 2,
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "content": (
            "Students requesting scholarship assistance must "
            "submit a support ticket under Financial Aid. "
            "The Financial Aid Team reviews the request and "
            "provides the applicable application guidance."
        ),
        "article_title": "Scholarship assistance for 2026"
    },
    {
        "category": "Registration",
        "title": "Course Registration Support",
        "version": 1,
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "content": (
            "Students experiencing course registration errors "
            "must submit a Registration support ticket. "
            "The Registration Team verifies the issue and "
            "provides instructions based on the current term."
        ),
        "article_title": "Resolving course registration issues"
    },
    {
        "category": "IT",
        "title": "Student Portal Access Support",
        "version": 1,
        "effective_from": "2025-01-01",
        "effective_to": "2025-12-31",
        "content": (
            "Student portal login problems are handled by "
            "the IT Support Team through a support request."
        ),
        "article_title": "Student portal access guidance for 2025"
    },
    {
        "category": "IT",
        "title": "Student Portal Access Support",
        "version": 2,
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "content": (
            "Students and faculty who cannot access the "
            "student portal should submit an IT support ticket. "
            "The IT Support Team verifies the account issue "
            "and provides approved password-reset or "
            "access-recovery instructions."
        ),
        "article_title": "Student portal access guidance for 2026"
    },
    {
        "category": "Accessibility",
        "title": "Accessibility Assistance Support",
        "version": 1,
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "content": (
            "Students and faculty requesting accessibility "
            "assistance should submit an Accessibility ticket. "
            "Accessibility Services reviews the request and "
            "coordinates appropriate support."
        ),
        "article_title": "Requesting accessibility assistance"
    }
]


def seed_policies():
    create_database()
    conn = get_connection()

    try:
        with conn:
            for item in POLICIES:
                category = conn.execute("""
                    SELECT category_id
                    FROM categories
                    WHERE category_name = ?
                """, (item["category"],)).fetchone()

                if category is None:
                    raise ValueError(
                        "Missing category: " + item["category"]
                    )

                category_id = category["category_id"]

                # Find the same policy version if it already exists.
                existing = conn.execute("""
                    SELECT policy_id
                    FROM policy_documents
                    WHERE title = ?
                      AND category_id = ?
                      AND version = ?
                """, (
                    item["title"],
                    category_id,
                    item["version"]
                )).fetchone()

                if existing:
                    policy_id = existing["policy_id"]
                else:
                    cursor = conn.execute("""
                        INSERT INTO policy_documents (
                            title,
                            category_id,
                            version,
                            content,
                            effective_from,
                            effective_to
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        item["title"],
                        category_id,
                        item["version"],
                        item["content"],
                        item["effective_from"],
                        item["effective_to"]
                    ))

                    policy_id = cursor.lastrowid

                # Set a deterministic policy code.
                category_code = {
                    "Financial Aid": "FIN",
                    "Registration": "REG",
                    "IT": "IT",
                    "Accessibility": "ACC"
                }[item["category"]]

                policy_code = (
                    f"POL-{category_code}-2026-"
                    f"{policy_id:03d}"
                )

                conn.execute("""
                    UPDATE policy_documents
                    SET policy_code = ?
                    WHERE policy_id = ?
                """, (policy_code, policy_id))

                # Create a linked knowledge article.
                existing_article = conn.execute("""
                    SELECT article_id
                    FROM knowledge_articles
                    WHERE policy_id = ?
                      AND title = ?
                """, (
                    policy_id,
                    item["article_title"]
                )).fetchone()

                if existing_article is None:
                    cursor = conn.execute("""
                        INSERT INTO knowledge_articles (
                            policy_id,
                            title,
                            content
                        )
                        VALUES (?, ?, ?)
                    """, (
                        policy_id,
                        item["article_title"],
                        item["content"]
                    ))

                    article_id = cursor.lastrowid

                    conn.execute("""
                        UPDATE knowledge_articles
                        SET article_code = ?
                        WHERE article_id = ?
                    """, (
                        f"KB-{article_id:06d}",
                        article_id
                    ))

        policy_count = conn.execute("""
            SELECT COUNT(*) FROM policy_documents
        """).fetchone()[0]

        article_count = conn.execute("""
            SELECT COUNT(*) FROM knowledge_articles
        """).fetchone()[0]

        active_count = conn.execute("""
            SELECT COUNT(*)
            FROM policy_documents
            WHERE effective_from <= ?
              AND (
                  effective_to IS NULL
                  OR effective_to >= ?
              )
        """, (
            date.today().isoformat(),
            date.today().isoformat()
        )).fetchone()[0]

        print("Policy seed completed successfully!")
        print("Total policy documents:", policy_count)
        print("Total knowledge articles:", article_count)
        print("Currently effective policies:", active_count)

    finally:
        conn.close()


if __name__ == "__main__":
    seed_policies()
