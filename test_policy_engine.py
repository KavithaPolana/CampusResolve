
import sqlite3
import unittest

from policy_engine import (
    find_policy,
    process_ticket_policy
)


class PolicyEngineTests(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.conn.executescript("""
            CREATE TABLE categories (
                category_id INTEGER PRIMARY KEY,
                category_name TEXT NOT NULL
            );

            CREATE TABLE tickets (
                ticket_id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (category_id)
                    REFERENCES categories(category_id)
            );

            CREATE TABLE policy_documents (
                policy_id INTEGER PRIMARY KEY,
                policy_code TEXT,
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT
            );

            CREATE TABLE knowledge_articles (
                article_id INTEGER PRIMARY KEY,
                article_code TEXT,
                policy_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            );

            CREATE TABLE messages (
                message_id INTEGER PRIMARY KEY,
                message_number TEXT,
                ticket_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                message_text TEXT NOT NULL,
                policy_id INTEGER,
                policy_version INTEGER,
                created_at TEXT
            );

            CREATE TABLE policy_citations (
                citation_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL,
                policy_id INTEGER NOT NULL,
                article_id INTEGER,
                cited_version INTEGER NOT NULL,
                cited_at TEXT
            );

            CREATE TABLE ticket_events (
                event_id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_description TEXT NOT NULL,
                created_at TEXT
            );

            INSERT INTO categories
            VALUES (1, 'IT');

            INSERT INTO tickets
            VALUES (
                1,
                1,
                'Cannot reset portal password',
                'Password reset link is not working',
                'Assigned',
                NULL
            );

            INSERT INTO policy_documents
            VALUES (
                1,
                'POL-IT-2026-001',
                1,
                'Student Portal Access Support',
                2,
                'Submit an IT support ticket for portal access recovery.',
                '2026-01-01',
                '2026-12-31'
            );

            INSERT INTO knowledge_articles
            VALUES (
                1,
                'KB-000001',
                1,
                'Student portal password access',
                'Approved IT portal recovery guidance.'
            );
        """)

    def tearDown(self):
        self.conn.close()

    def test_current_policy_selected(self):
        result = find_policy(
            1,
            self.conn,
            as_of="2026-10-29"
        )

        self.assertEqual(
            result["decision"],
            "SUPPORTED"
        )

        self.assertEqual(
            result["policy"]["version"],
            2
        )

    def test_expired_policy_rejected(self):
        result = find_policy(
            1,
            self.conn,
            as_of="2027-01-01"
        )

        self.assertEqual(
            result["decision"],
            "ESCALATE"
        )

    def test_unsupported_question_escalates(self):
        self.conn.execute("""
            UPDATE tickets
            SET subject = 'Parking permit',
                description = 'Where can I park my bicycle?'
            WHERE ticket_id = 1
        """)

        result = find_policy(
            1,
            self.conn,
            as_of="2026-10-29"
        )

        self.assertEqual(
            result["decision"],
            "ESCALATE"
        )

    def test_answer_has_citation(self):
        result = process_ticket_policy(
            1,
            self.conn,
            as_of="2026-10-29"
        )

        self.assertEqual(
            result["decision"],
            "SUPPORTED"
        )

        citation = self.conn.execute("""
            SELECT policy_id, cited_version
            FROM policy_citations
        """).fetchone()

        self.assertIsNotNone(citation)
        self.assertEqual(citation["policy_id"], 1)
        self.assertEqual(citation["cited_version"], 2)

    def test_duplicate_answer_prevented(self):
        process_ticket_policy(
            1,
            self.conn,
            as_of="2026-10-29"
        )

        second = process_ticket_policy(
            1,
            self.conn,
            as_of="2026-10-29"
        )

        self.assertEqual(
            second["decision"],
            "ALREADY_PROCESSED"
        )

        count = self.conn.execute("""
            SELECT COUNT(*) FROM messages
        """).fetchone()[0]

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
