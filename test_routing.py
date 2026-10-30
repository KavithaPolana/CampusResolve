
import sqlite3
import unittest

from routing_engine import route_ticket


class RoutingEngineTests(unittest.TestCase):

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
                status TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (category_id)
                    REFERENCES categories(category_id)
            );

            CREATE TABLE routing_rules (
                rule_id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                is_authorized INTEGER NOT NULL
            );

            CREATE TABLE assignments (
                assignment_id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                assigned_team TEXT NOT NULL,
                assigned_at TEXT
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
            VALUES (1, 1, 'Open', NULL);

            INSERT INTO routing_rules
            VALUES (1, 1, 'IT Support Team', 1);
        """)

    def tearDown(self):
        self.conn.close()

    def test_authorized_routing(self):
        result = route_ticket(1, self.conn)

        self.assertEqual(
            result["decision"],
            "AUTHORIZED_ROUTE"
        )

        self.assertEqual(
            result["assigned_team"],
            "IT Support Team"
        )

        self.assertEqual(
            result["status"],
            "Assigned"
        )

        assignment_count = self.conn.execute("""
            SELECT COUNT(*) FROM assignments
        """).fetchone()[0]

        self.assertEqual(assignment_count, 1)

    def test_no_authorized_team_escalates(self):
        self.conn.execute("""
            UPDATE routing_rules
            SET is_authorized = 0
        """)

        result = route_ticket(1, self.conn)

        self.assertEqual(
            result["decision"],
            "NO_AUTHORIZED_TEAM"
        )

        self.assertEqual(
            result["status"],
            "Escalated"
        )

        assignment_count = self.conn.execute("""
            SELECT COUNT(*) FROM assignments
        """).fetchone()[0]

        self.assertEqual(assignment_count, 0)

    def test_duplicate_routing_prevented(self):
        first = route_ticket(1, self.conn)
        second = route_ticket(1, self.conn)

        self.assertEqual(
            first["decision"],
            "AUTHORIZED_ROUTE"
        )

        self.assertEqual(
            second["decision"],
            "ALREADY_ROUTED"
        )

        assignment_count = self.conn.execute("""
            SELECT COUNT(*) FROM assignments
        """).fetchone()[0]

        self.assertEqual(assignment_count, 1)

    def test_missing_ticket(self):
        with self.assertRaises(ValueError):
            route_ticket(999, self.conn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
