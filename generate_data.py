"""CampusResolve deterministic synthetic baseline generator.

Run: python generate_data.py
Creates synthetic_campusresolve.db without modifying campusresolve.db.
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import database

SEED = 20261022
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'synthetic_campusresolve.db'
TICKET_COUNT = 5000
ARTICLE_COUNT = 200
MESSAGE_COUNT = 20000

TOPICS = {
    'Financial Aid': [
        ('Scholarship application', 'Applicants must submit a completed scholarship application and required documents before the published deadline.'),
        ('Financial aid eligibility', 'Eligibility is assessed by the Financial Aid Team using the applicable award criteria and submitted evidence.'),
        ('Tuition assistance', 'Tuition assistance requests are reviewed by the Financial Aid Team after the student provides the required supporting documents.'),
        ('Scholarship status', 'Students can request the current status of a submitted scholarship application through the Financial Aid Team.'),
    ],
    'Registration': [
        ('Course registration', 'Students should use the registration portal during the published enrollment window to register for eligible courses.'),
        ('Registration deadline', 'Late registration requires review by the Registration Team and is not guaranteed.'),
        ('Enrollment verification', 'Enrollment verification is issued after registration records have been confirmed by the Registration Team.'),
        ('Course change', 'Course change requests are subject to available seats and the published add-drop period.'),
    ],
    'IT': [
        ('Student portal password reset', 'Students unable to access the student portal should submit an IT support request for approved password-reset assistance.'),
        ('Account recovery', 'The IT Support Team verifies account ownership before providing approved account-recovery instructions.'),
        ('Campus Wi-Fi access', 'Campus Wi-Fi connection issues should be reported to IT with the device type and location.'),
        ('Learning platform login', 'Learning platform login problems are reviewed by IT after the requester supplies the affected account and error description.'),
    ],
    'Accessibility': [
        ('Accessibility accommodation', 'Accessibility accommodation requests are reviewed confidentially by Accessibility Services based on documented needs.'),
        ('Assistive technology', 'Requests for approved assistive technology are assessed by Accessibility Services for suitability and availability.'),
        ('Accessible classroom', 'Accessible classroom arrangements are coordinated by Accessibility Services with the relevant academic department.'),
        ('Accessible course materials', 'Students may request accessible course materials through Accessibility Services for review and coordination.'),
    ],
}


def business_deadline(start, hours):
    """Add business hours using Monday-Friday 09:00-17:00 local clock time."""
    moment = start
    remaining = hours * 3600
    while remaining:
        if moment.weekday() >= 5:
            moment = (moment + timedelta(days=1)).replace(hour=9, minute=0, second=0)
            continue
        opening = moment.replace(hour=9, minute=0, second=0)
        closing = moment.replace(hour=17, minute=0, second=0)
        if moment < opening:
            moment = opening
        if moment >= closing:
            moment = (moment + timedelta(days=1)).replace(hour=9, minute=0, second=0)
            continue
        available = int((closing - moment).total_seconds())
        consumed = min(available, remaining)
        moment += timedelta(seconds=consumed)
        remaining -= consumed
    return moment.strftime('%Y-%m-%d %H:%M:%S')


def main():
    rng = random.Random(SEED)
    if OUTPUT.exists():
        print('Dataset already exists:', OUTPUT)
        print('Delete synthetic_campusresolve.db only if you want to regenerate it.')
        return

    # Reuse the actual CampusResolve schema while redirecting only this
    # initialization to a new database. Never touch the live database.
    original_path = database.DB_PATH
    try:
        database.DB_PATH = OUTPUT
        database.create_database()
    finally:
        database.DB_PATH = original_path

    conn = sqlite3.connect(OUTPUT)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    stamp = lambda value: value.strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn.execute('BEGIN')
        for term, start, end in [
            ('Spring 2026', '2026-01-01', '2026-05-31'),
            ('Summer 2026', '2026-06-01', '2026-07-31'),
            ('Fall 2026', '2026-08-01', '2026-12-31'),
        ]:
            conn.execute('INSERT INTO terms (term_name, start_date, end_date) VALUES (?, ?, ?)', (term, start, end))
        term_ids = [r['term_id'] for r in conn.execute('SELECT term_id FROM terms ORDER BY term_id')]
        role_ids = {r['role_name']: r['role_id'] for r in conn.execute('SELECT * FROM roles')}
        categories = [dict(r) for r in conn.execute('SELECT * FROM categories ORDER BY category_id')]

        for index in range(1, 501):
            role = 'Faculty' if index % 6 == 0 else 'Student'
            conn.execute('INSERT INTO requesters (name, email, role_id) VALUES (?, ?, ?)',
                         (f'Synthetic Requester {index:04d}', f'synthetic{index:04d}@example.edu', role_ids[role]))
        requester_ids = [r['requester_id'] for r in conn.execute('SELECT requester_id FROM requesters ORDER BY requester_id')]

        # 200 synthetic knowledge articles; each cites its own versioned policy.
        policy_for_topic = {}
        article_index = 0
        for category in categories:
            category_name = category['category_name']
            domain = category_name.upper().replace(' ', '-')
            for j in range(50):
                article_index += 1
                topic_index = j % len(TOPICS[category_name])
                title, guidance = TOPICS[category_name][topic_index]
                variant = j // len(TOPICS[category_name]) + 1
                version = 1 + (j % 2)
                code = f'POL-{domain}-2026-{j+1:03d}'
                cursor = conn.execute('''INSERT INTO policy_documents
                    (title, category_id, version, content, effective_from, effective_to, policy_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (f'{title} policy edition {variant}', category['category_id'], version,
                     guidance, '2026-01-01', None, code))
                policy_id = cursor.lastrowid
                article_cursor = conn.execute('''INSERT INTO knowledge_articles
                    (policy_id, title, content, article_code) VALUES (?, ?, ?, ?)''',
                    (policy_id, f'{title} guide {variant}', guidance, f'KB-{article_index:06d}'))
                policy_for_topic.setdefault((category_name, topic_index),
                                            (policy_id, article_cursor.lastrowid, version, code, guidance))

        statuses = {'Resolved': 0, 'Escalated': 0, 'In Progress': 0, 'Assigned': 0}
        base = datetime(2026, 4, 1, 9)
        for ticket_index in range(1, TICKET_COUNT + 1):
            category = categories[(ticket_index - 1) % len(categories)]
            category_name = category['category_name']
            topic_index = (ticket_index // 4) % len(TOPICS[category_name])
            topic, guidance = TOPICS[category_name][topic_index]
            created = base + timedelta(days=rng.randrange(0, 195), hours=rng.randrange(0, 9), minutes=rng.randrange(0, 60))
            # A documented decision rule: ambiguous or unlisted requests escalate;
            # other requests resolve when their simulated service history completes.
            is_ambiguous = ticket_index % 17 == 0
            is_urgent = ticket_index % 23 == 0
            resolved = not is_ambiguous and ticket_index % 7 != 0
            status = 'Escalated' if is_ambiguous else ('Resolved' if resolved else 'In Progress')
            statuses[status] += 1
            subject = (f'Unlisted {topic.lower()} exception' if is_ambiguous
                       else f'{topic} request')
            description = (f'Please review this unusual request for {topic.lower()}; '
                           'the approved guidance does not address my circumstances.' if is_ambiguous
                           else f'I need assistance with {topic.lower()}.' +
                           (' My deadline is urgent.' if is_urgent else ''))
            updated = created + timedelta(hours=6 if resolved else 2)
            cursor = conn.execute('''INSERT INTO tickets
                (requester_id, category_id, term_id, subject, description, status,
                 created_at, updated_at, ticket_number, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (rng.choice(requester_ids), category['category_id'],
                 term_ids[0 if created.month <= 5 else (1 if created.month <= 7 else 2)],
                 subject, description, status, stamp(created), stamp(updated),
                 f'TKT-2026-{ticket_index:06d}', 'High' if is_urgent else 'Normal'))
            ticket_id = cursor.lastrowid
            conn.execute('INSERT INTO assignments (ticket_id, assigned_team, assigned_at) VALUES (?, ?, ?)',
                         (ticket_id, category['support_team'], stamp(created)))
            conn.execute('''INSERT INTO sla (ticket_id, response_deadline, resolution_deadline,
                first_response_at, resolved_at, sla_code, breached) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (ticket_id, business_deadline(created, 2),
                 business_deadline(created, category['resolution_hours']),
                 stamp(created + timedelta(minutes=30)), stamp(updated) if resolved else None,
                 f'SLA-TKT-2026-{ticket_index:06d}', 0))
            conn.execute('''INSERT INTO ticket_events
                (ticket_id, event_type, event_description, created_at) VALUES (?, ?, ?, ?)''',
                (ticket_id, 'Created', 'Synthetic request submitted.', stamp(created)))
            conn.execute('''INSERT INTO ticket_events
                (ticket_id, event_type, event_description, created_at) VALUES (?, ?, ?, ?)''',
                (ticket_id, 'Auto Assigned', f'Routed to {category["support_team"]} by authorized category rule.', stamp(created)))
            policy_id, article_id, version, code, policy_content = policy_for_topic[(category_name, topic_index)]
            for msg_index in range(1, 5):
                when = created + timedelta(minutes=15 * msg_index)
                if msg_index == 1:
                    sender, content, cited = 'Requester', description, False
                elif msg_index == 2 and not is_ambiguous:
                    sender, content, cited = 'Automated Support', policy_content + f'\nSource: {code}, version {version}', True
                elif msg_index == 2:
                    sender, content, cited = 'Automated Support', 'No applicable policy found; sent for human review.', False
                elif msg_index == 3:
                    sender, content, cited = 'Support Agent', 'Your request has been reviewed by the assigned team.', False
                else:
                    sender, content, cited = 'Support Agent', ('The request was resolved under approved guidance.' if resolved
                        else 'The request remains under review or escalation.'), False
                message_cursor = conn.execute('''INSERT INTO messages
                    (ticket_id, sender_type, message_text, policy_id, policy_version, created_at, message_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (ticket_id, sender, content, policy_id if cited else None,
                     version if cited else None, stamp(when), f'MSG-{ticket_index:06d}-{msg_index:03d}'))
                if cited:
                    conn.execute('''INSERT INTO policy_citations
                        (message_id, policy_id, article_id, cited_version, cited_at)
                        VALUES (?, ?, ?, ?, ?)''',
                        (message_cursor.lastrowid, policy_id, article_id, version, stamp(when)))
            if resolved:
                conn.execute('''INSERT INTO resolution_feedback
                    (ticket_id, resolution_note, resolved_at) VALUES (?, ?, ?)''',
                    (ticket_id, 'Resolved using approved category guidance.', stamp(updated)))
            if is_ambiguous:
                conn.execute('''INSERT INTO ticket_events
                    (ticket_id, event_type, event_description, created_at) VALUES (?, ?, ?, ?)''',
                    (ticket_id, 'Policy Escalation', 'Unlisted request requires human review.', stamp(created + timedelta(minutes=30))))
        errors = conn.execute('PRAGMA foreign_key_check').fetchall()
        if errors:
            raise RuntimeError(f'Foreign key violations: {len(errors)}')
        for table, expected in [('tickets', TICKET_COUNT), ('knowledge_articles', ARTICLE_COUNT), ('messages', MESSAGE_COUNT)]:
            actual = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            if actual != expected:
                raise RuntimeError(f'{table}: expected {expected}, found {actual}')
        conn.commit()
        print('Synthetic baseline generated:', OUTPUT)
        print('Seed:', SEED)
        print('Tickets: 5000 | Knowledge articles: 200 | Messages: 20000')
        print('Outcome counts:', statuses)
        print('Foreign key violations: 0')
        print('Next: generate labelled negative cases and separate ground truth.')
    except Exception:
        conn.rollback()
        conn.close()
        OUTPUT.unlink(missing_ok=True)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
