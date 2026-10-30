
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "campusresolve.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def column_exists(conn, table_name, column_name):
    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        column["name"] == column_name
        for column in columns
    )


def add_column_if_missing(conn, table_name, column_name, definition):
    if not column_exists(conn, table_name, column_name):
        conn.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )


def create_database():
    conn = get_connection()

    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS roles (
            role_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS requesters (
            requester_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role_id INTEGER NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(role_id)
        );

        CREATE TABLE IF NOT EXISTS terms (
            term_id INTEGER PRIMARY KEY AUTOINCREMENT,
            term_name TEXT NOT NULL UNIQUE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE,
            support_team TEXT NOT NULL,
            resolution_hours INTEGER NOT NULL
                CHECK (resolution_hours > 0)
        );

        CREATE TABLE IF NOT EXISTS policy_documents (
            policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            content TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            FOREIGN KEY (category_id)
                REFERENCES categories(category_id)
        );

        CREATE TABLE IF NOT EXISTS knowledge_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (policy_id)
                REFERENCES policy_documents(policy_id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            term_id INTEGER,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open'
                CHECK (status IN (
                    'Open',
                    'Assigned',
                    'In Progress',
                    'Escalated',
                    'Resolved',
                    'Closed'
                )),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requester_id)
                REFERENCES requesters(requester_id),
            FOREIGN KEY (category_id)
                REFERENCES categories(category_id),
            FOREIGN KEY (term_id)
                REFERENCES terms(term_id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            assigned_team TEXT NOT NULL,
            assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id)
                REFERENCES tickets(ticket_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            message_text TEXT NOT NULL,
            policy_id INTEGER,
            policy_version INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id)
                REFERENCES tickets(ticket_id),
            FOREIGN KEY (policy_id)
                REFERENCES policy_documents(policy_id)
        );

        CREATE TABLE IF NOT EXISTS sla (
            sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL UNIQUE,
            response_deadline TEXT NOT NULL,
            resolution_deadline TEXT NOT NULL,
            first_response_at TEXT,
            resolved_at TEXT,
            FOREIGN KEY (ticket_id)
                REFERENCES tickets(ticket_id)
        );

        CREATE TABLE IF NOT EXISTS resolution_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            resolution_note TEXT NOT NULL,
            resolved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id)
                REFERENCES tickets(ticket_id)
        );

        CREATE TABLE IF NOT EXISTS ticket_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id)
                REFERENCES tickets(ticket_id)
        );

        CREATE TABLE IF NOT EXISTS routing_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            is_authorized INTEGER NOT NULL DEFAULT 1
                CHECK (is_authorized IN (0, 1)),
            UNIQUE(category_id, team_name),
            FOREIGN KEY (category_id)
                REFERENCES categories(category_id)
        );

        CREATE TABLE IF NOT EXISTS policy_citations (
            citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            policy_id INTEGER NOT NULL,
            article_id INTEGER,
            cited_version INTEGER NOT NULL,
            cited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id)
                REFERENCES messages(message_id),
            FOREIGN KEY (policy_id)
                REFERENCES policy_documents(policy_id),
            FOREIGN KEY (article_id)
                REFERENCES knowledge_articles(article_id)
        );

        CREATE TABLE IF NOT EXISTS sla_business_hours (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL
                CHECK (weekday BETWEEN 0 AND 6),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_working_day INTEGER NOT NULL
                CHECK (is_working_day IN (0, 1)),
            UNIQUE(weekday)
        );

        CREATE INDEX IF NOT EXISTS idx_tickets_status
            ON tickets(status);

        CREATE INDEX IF NOT EXISTS idx_tickets_category
            ON tickets(category_id);

        CREATE INDEX IF NOT EXISTS idx_messages_ticket
            ON messages(ticket_id);

        CREATE INDEX IF NOT EXISTS idx_events_ticket
            ON ticket_events(ticket_id);

        CREATE INDEX IF NOT EXISTS idx_citations_message
            ON policy_citations(message_id);
        """)

        # Add fields without deleting existing data.
        add_column_if_missing(
            conn, "tickets", "ticket_number", "TEXT"
        )

        add_column_if_missing(
            conn, "tickets", "priority",
            "TEXT NOT NULL DEFAULT 'Normal'"
        )

        add_column_if_missing(
            conn, "messages", "message_number", "TEXT"
        )

        add_column_if_missing(
            conn, "policy_documents", "policy_code", "TEXT"
        )

        add_column_if_missing(
            conn, "knowledge_articles", "article_code", "TEXT"
        )

        add_column_if_missing(
            conn, "sla", "sla_code", "TEXT"
        )

        add_column_if_missing(
            conn, "sla", "breached",
            "INTEGER NOT NULL DEFAULT 0"
        )

        # Required roles and categories.
        roles = [
            ("Student",),
            ("Faculty",),
            ("Support Agent",),
            ("Administrator",),
            ("Academic Administrator",)
        ]

        categories = [
            ("Financial Aid", "Financial Aid Team", 16),
            ("Registration", "Registration Team", 16),
            ("IT", "IT Support Team", 8),
            ("Accessibility", "Accessibility Services", 24)
        ]

        conn.executemany(
            "INSERT OR IGNORE INTO roles (role_name) VALUES (?)",
            roles
        )

        conn.executemany("""
            INSERT OR IGNORE INTO categories
            (category_name, support_team, resolution_hours)
            VALUES (?, ?, ?)
        """, categories)

        # Create authorized routing rules.
        conn.execute("""
            INSERT OR IGNORE INTO routing_rules (
                category_id,
                team_name,
                is_authorized
            )
            SELECT
                category_id,
                support_team,
                1
            FROM categories
        """)

        # Example business-hours schedule:
        # Monday-Friday, 09:00-17:00.
        # This is configurable, not a schedule specified
        # by the challenge screenshots.
        for weekday in range(7):
            is_working_day = 1 if weekday < 5 else 0

            conn.execute("""
                INSERT OR IGNORE INTO sla_business_hours (
                    weekday,
                    start_time,
                    end_time,
                    is_working_day
                )
                VALUES (?, '09:00', '17:00', ?)
            """, (weekday, is_working_day))

        # Assign deterministic public IDs to existing records.
        conn.execute("""
            UPDATE tickets
            SET ticket_number =
                'TKT-' ||
                strftime('%Y', created_at) ||
                '-' ||
                printf('%06d', ticket_id)
            WHERE ticket_number IS NULL
        """)

        conn.execute("""
            UPDATE messages
            SET message_number =
                'MSG-' ||
                ticket_id ||
                '-' ||
                printf(
                    '%03d',
                    (
                        SELECT COUNT(*)
                        FROM messages AS previous
                        WHERE previous.ticket_id = messages.ticket_id
                          AND previous.message_id <= messages.message_id
                    )
                )
            WHERE message_number IS NULL
        """)

        conn.execute("""
            UPDATE knowledge_articles
            SET article_code =
                'KB-' || printf('%06d', article_id)
            WHERE article_code IS NULL
        """)

        conn.execute("""
            UPDATE sla
            SET sla_code =
                'SLA-' ||
                (
                    SELECT ticket_number
                    FROM tickets
                    WHERE tickets.ticket_id = sla.ticket_id
                )
            WHERE sla_code IS NULL
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_tickets_ticket_number
            ON tickets(ticket_number)
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_messages_message_number
            ON messages(message_number)
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_articles_article_code
            ON knowledge_articles(article_code)
        """)

        conn.commit()

        table_count = conn.execute("""
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
        """).fetchone()[0]

        ticket_count = conn.execute("""
            SELECT COUNT(*) FROM tickets
        """).fetchone()[0]

        errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("CampusResolve database upgraded successfully!")
        print("Database file:", DB_PATH)
        print("Total tables:", table_count)
        print("Existing tickets preserved:", ticket_count)
        print("Foreign key errors:", len(errors))

    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
