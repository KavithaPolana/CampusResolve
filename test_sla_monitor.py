
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from sla_monitor import check_sla_breaches


class SLAMonitorTests(unittest.TestCase):

    def setUp(self):
        """
        Create a temporary SQLite database
        for every test.
        """
        self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = (
            Path(self.temp_dir.name) / "test_sla.db"
        )

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.conn.executescript("""
            CREATE TABLE tickets (
                ticket_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                updated_at TEXT
            );

            CREATE TABLE sla (
                sla_id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL UNIQUE,
                response_deadline TEXT NOT NULL,
                resolution_deadline TEXT NOT NULL,
                first_response_at TEXT,
                resolved_at TEXT,
                FOREIGN KEY (ticket_id)
                    REFERENCES tickets(ticket_id)
            );

            CREATE TABLE ticket_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id)
                    REFERENCES tickets(ticket_id)
            );
        """)

        self.now = datetime(
            2026, 10, 30, 12, 0, 0
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def add_ticket(
        self,
        ticket_id,
        status="Assigned",
        response_deadline=None,
        resolution_deadline=None,
        first_response_at=None,
        resolved_at=None
    ):
        """
        Insert a test ticket and its SLA record.
        """
        response_deadline = (
            response_deadline
            or self.now + timedelta(hours=2)
        )

        resolution_deadline = (
            resolution_deadline
            or self.now + timedelta(hours=8)
        )

        self.conn.execute("""
            INSERT INTO tickets (
                ticket_id,
                status,
                updated_at
            )
            VALUES (?, ?, ?)
        """, (
            ticket_id,
            status,
            self.now.strftime("%Y-%m-%d %H:%M:%S")
        ))

        self.conn.execute("""
            INSERT INTO sla (
                ticket_id,
                response_deadline,
                resolution_deadline,
                first_response_at,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            ticket_id,
            response_deadline.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            resolution_deadline.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            first_response_at,
            resolved_at
        ))

        self.conn.commit()

    def test_no_breach_before_deadline(self):
        """
        A ticket must not escalate before its deadline.
        """
        self.add_ticket(ticket_id=1)

        result = check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        status = self.conn.execute("""
            SELECT status
            FROM tickets
            WHERE ticket_id = 1
        """).fetchone()["status"]

        self.assertEqual(status, "Assigned")
        self.assertEqual(
            result["tickets_escalated"], 0
        )
        self.assertEqual(
            result["response_breaches"], 0
        )

    def test_missed_response_escalates(self):
        """
        A missed first response must trigger escalation.
        """
        self.add_ticket(
            ticket_id=2,
            response_deadline=(
                self.now - timedelta(hours=1)
            )
        )

        result = check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        status = self.conn.execute("""
            SELECT status
            FROM tickets
            WHERE ticket_id = 2
        """).fetchone()["status"]

        self.assertEqual(status, "Escalated")
        self.assertEqual(
            result["response_breaches"], 1
        )
        self.assertEqual(
            result["tickets_escalated"], 1
        )

    def test_missed_resolution_escalates(self):
        """
        A missed resolution deadline must escalate.
        """
        self.add_ticket(
            ticket_id=3,
            resolution_deadline=(
                self.now - timedelta(hours=1)
            ),
            first_response_at=(
                self.now - timedelta(hours=4)
            ).strftime("%Y-%m-%d %H:%M:%S")
        )

        result = check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        self.assertEqual(
            result["resolution_breaches"], 1
        )
        self.assertEqual(
            result["tickets_escalated"], 1
        )

    def test_duplicate_events_prevented(self):
        """
        Running the monitor twice must not
        duplicate the same breach event.
        """
        self.add_ticket(
            ticket_id=4,
            response_deadline=(
                self.now - timedelta(hours=1)
            )
        )

        check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        second_result = check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        count = self.conn.execute("""
            SELECT COUNT(*)
            FROM ticket_events
            WHERE ticket_id = 4
              AND event_type = 'SLA Response Breach'
        """).fetchone()[0]

        self.assertEqual(count, 1)
        self.assertEqual(
            second_result["response_breaches"], 0
        )
        self.assertEqual(
            second_result["tickets_escalated"], 0
        )

    def test_resolved_ticket_not_escalated(self):
        """
        A resolved ticket must remain resolved.
        """
        self.add_ticket(
            ticket_id=5,
            status="Resolved",
            response_deadline=(
                self.now - timedelta(hours=3)
            ),
            resolution_deadline=(
                self.now - timedelta(hours=1)
            )
        )

        result = check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        status = self.conn.execute("""
            SELECT status
            FROM tickets
            WHERE ticket_id = 5
        """).fetchone()["status"]

        self.assertEqual(status, "Resolved")
        self.assertEqual(
            result["tickets_escalated"], 0
        )

    def test_breach_history_recorded(self):
        """
        Escalation must be traceable through events.
        """
        self.add_ticket(
            ticket_id=6,
            response_deadline=(
                self.now - timedelta(hours=1)
            )
        )

        check_sla_breaches(
            conn=self.conn,
            now=self.now
        )

        events = self.conn.execute("""
            SELECT event_type
            FROM ticket_events
            WHERE ticket_id = 6
            ORDER BY event_id
        """).fetchall()

        event_types = [
            row["event_type"]
            for row in events
        ]

        self.assertIn(
            "SLA Response Breach",
            event_types
        )

        self.assertIn(
            "SLA Auto Escalation",
            event_types
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
