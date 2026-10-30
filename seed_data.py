
from database import get_connection, create_database


def seed_data():
    create_database()
    conn = get_connection()

    try:
        requesters = [
            ("Ananya Rao", "ananya.rao@example.edu", "Student"),
            ("Rahul Sharma", "rahul.sharma@example.edu", "Student"),
            ("Priya Reddy", "priya.reddy@example.edu", "Student"),
            ("Arjun Kumar", "arjun.kumar@example.edu", "Student"),
            ("Sneha Patel", "sneha.patel@example.edu", "Student"),
            ("Dr. Meera Nair", "meera.nair@example.edu", "Faculty"),
            ("Dr. Vikram Rao", "vikram.rao@example.edu", "Faculty"),
            ("Prof. Kavya Menon", "kavya.menon@example.edu", "Faculty")
        ]

        for name, email, role_name in requesters:
            role = conn.execute(
                "SELECT role_id FROM roles WHERE role_name = ?",
                (role_name,)
            ).fetchone()

            if role is None:
                raise ValueError(f"Role not found: {role_name}")

            conn.execute("""
                INSERT OR IGNORE INTO requesters
                (name, email, role_id)
                VALUES (?, ?, ?)
            """, (name, email, role["role_id"]))

        terms = [
            ("Spring 2026", "2026-01-01", "2026-05-31"),
            ("Summer 2026", "2026-06-01", "2026-08-31"),
            ("Fall 2026", "2026-09-01", "2026-12-31")
        ]

        conn.executemany("""
            INSERT OR IGNORE INTO terms
            (term_name, start_date, end_date)
            VALUES (?, ?, ?)
        """, terms)

        conn.commit()

        requester_count = conn.execute(
            "SELECT COUNT(*) FROM requesters"
        ).fetchone()[0]

        term_count = conn.execute(
            "SELECT COUNT(*) FROM terms"
        ).fetchone()[0]

        print("\nCampusResolve sample data added successfully!")
        print("Total requesters:", requester_count)
        print("Total academic terms:", term_count)

    finally:
        conn.close()


if __name__ == "__main__":
    seed_data()
