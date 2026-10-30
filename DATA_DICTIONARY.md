# CampusResolve — Data Dictionary

## 1. Overview

CampusResolve uses SQLite to manage student and faculty support requests, policy documents, knowledge articles, routing assignments, SLA deadlines, conversations, and ticket activity.

The project maintains two main databases:

- `campusresolve.db` — live application tickets created through the website.
- `synthetic_campusresolve.db` — deterministic synthetic dataset containing 5,000 tickets.

A separate database, `synthetic_campusresolve_negative.db`, contains five intentionally injected negative test cases.

The schema contains **15 relational tables**.

## 2. Database Tables

| Table | Primary Key | Purpose |
|---|---|---|
| `roles` | `role_id` | Stores user roles |
| `requesters` | `requester_id` | Stores ticket requesters |
| `terms` | `term_id` | Stores academic terms |
| `categories` | `category_id` | Stores support categories |
| `policy_documents` | `policy_id` | Stores versioned policies |
| `knowledge_articles` | `article_id` | Stores support knowledge |
| `tickets` | `ticket_id` | Stores support requests |
| `assignments` | `assignment_id` | Tracks team assignments |
| `messages` | `message_id` | Stores ticket conversations |
| `sla` | `sla_id` | Stores SLA deadlines and outcomes |
| `resolution_feedback` | `feedback_id` | Stores resolution information |
| `ticket_events` | `event_id` | Tracks ticket activity |
| `routing_rules` | See schema | Defines authorized team routing |
| `policy_citations` | See schema | Links tickets and policy references |
| `sla_business_hours` | See schema | Defines SLA working hours |

For tables marked *See schema*, refer to `database.py` for the exact primary-key and uniqueness definitions.

## 3. Core Entities and Fields

### Roles

**Table:** `roles`

| Field | Description |
|---|---|
| `role_id` | Unique role identifier |
| `role_name` | Name of the role |

The system supports roles such as Student, Faculty, Academic Administrator, Support Staff, and Platform Administrator.

### Requesters

**Table:** `requesters`

| Field | Description |
|---|---|
| `requester_id` | Unique requester identifier |
| `role_id` | References the requester's role |
| `name` | Requester display name |

Each requester is associated with a role. A requester may submit multiple tickets.

### Academic Terms

**Table:** `terms`

| Field | Description |
|---|---|
| `term_id` | Unique academic term identifier |

Academic terms provide context for campus support activity. Additional term attributes are defined in `database.py`.

### Categories

**Table:** `categories`

| Field | Description |
|---|---|
| `category_id` | Unique category identifier |
| `category_name` | Support category name |

The four service categories are Financial Aid, Registration, IT, and Accessibility.

### Policy Documents

**Table:** `policy_documents`

| Field | Description |
|---|---|
| `policy_id` | Unique policy identifier |
| `policy_code` | Public policy reference |
| `title` | Policy title |
| `category_id` | Related support category |
| `version` | Policy version |
| `content` | Policy guidance |
| `effective_from` | Start of policy validity |
| `effective_to` | End of policy validity, when specified |

Policy references use a format such as `POL-ACCESSIBILITY-2026-003`.

Policy validity is evaluated using effective dates and policy version information.

### Knowledge Articles

**Table:** `knowledge_articles`

| Field | Description |
|---|---|
| `article_id` | Unique article identifier |

Knowledge articles provide support information associated with campus requests. Their additional fields and relationships are defined in the SQLite schema.

### Tickets

**Table:** `tickets`

| Field | Description |
|---|---|
| `ticket_id` | Internal unique ticket identifier |
| `ticket_number` | Public ticket identifier |
| `requester_id` | Requester who submitted the ticket |
| `category_id` | Support category |
| `subject` | Ticket subject |
| `description` | Request details |
| `status` | Current ticket lifecycle state |
| `created_at` | Ticket creation timestamp |
| `updated_at` | Last update timestamp |

Ticket numbers follow the format `TKT-2026-000001`.

Supported lifecycle states are:

- Open
- Assigned
- In Progress
- Escalated
- Resolved
- Closed

### Assignments

**Table:** `assignments`

| Field | Description |
|---|---|
| `assignment_id` | Unique assignment identifier |
| `ticket_id` | Related ticket |
| `assigned_team` | Responsible support team |
| `assigned_at` | Assignment timestamp |

Assignment decisions are checked against authorized routing rules.

### Messages

**Table:** `messages`

| Field | Description |
|---|---|
| `message_id` | Internal message identifier |
| `ticket_id` | Related ticket |
| `sender_type` | Requester, automated support, or support agent |
| `message_text` | Message content |
| `policy_id` | Referenced policy, when applicable |
| `policy_version` | Policy version associated with the message |
| `message_number` | Message sequence within the ticket |
| `created_at` | Message timestamp |

A ticket can have multiple messages.

Policy-related messages can reference a specific policy and version.

### Service Level Agreements

**Table:** `sla`

| Field | Description |
|---|---|
| `sla_id` | Internal SLA identifier |
| `sla_code` | Public SLA identifier |
| `ticket_id` | Related ticket |
| `response_deadline` | Required first-response deadline |
| `resolution_deadline` | Required resolution deadline |
| `first_response_at` | Actual first-response timestamp |
| `resolved_at` | Actual resolution timestamp |
| `breached` | Recorded SLA breach indicator |

SLA codes use a format such as `SLA-TKT-2026-000001`.

Deadlines are calculated using configured business hours rather than treating all calendar hours as working hours.

### Resolution Feedback

**Table:** `resolution_feedback`

| Field | Description |
|---|---|
| `feedback_id` | Unique feedback identifier |
| `ticket_id` | Related ticket |
| `resolution_note` | Resolution details |
| `resolved_at` | Resolution timestamp |

Resolution records document the outcome of completed support requests.

### Ticket Events

**Table:** `ticket_events`

| Field | Description |
|---|---|
| `event_id` | Unique event identifier |
| `ticket_id` | Related ticket |
| `event_type` | Type of activity |
| `event_description` | Description of the event |
| `created_at` | Event timestamp |

Events provide a chronological activity history, including creation, assignment, and escalation activity.

### Routing Rules

**Table:** `routing_rules`

| Field | Description |
|---|---|
| `category_id` | Support category |
| `team_name` | Support team |
| `is_authorized` | Whether the team is permitted for the category |

Routing rules determine which teams can receive particular types of tickets.

### Policy Citations

**Table:** `policy_citations`

This table stores policy citation relationships for traceability.

Its exact columns, keys, and foreign-key constraints are defined in `database.py`.

### SLA Business Hours

**Table:** `sla_business_hours`

This table stores the configured working schedule used for SLA calculations.

The project's SLA engine uses Monday–Friday, 9:00 AM–5:00 PM IST.

Its exact columns and constraints are defined in `database.py`.

## 4. Main Relationships

| Parent Entity | Child Entity | Relationship |
|---|---|---|
| Roles | Requesters | One role to many requesters |
| Requesters | Tickets | One requester to many tickets |
| Categories | Tickets | One category to many tickets |
| Categories | Policy Documents | One category to many policies |
| Tickets | Messages | One ticket to many messages |
| Tickets | Assignments | One ticket to many assignment records |
| Tickets | Ticket Events | One ticket to many events |
| Tickets | SLA | One ticket to an associated SLA record in the generated dataset |
| Tickets | Resolution Feedback | Resolved tickets can have resolution records |
| Policy Documents | Messages | A policy may be referenced by multiple messages |

Some relationships are optional. For example, a message does not always need a policy citation, and an unresolved ticket does not necessarily have resolution feedback.

For the authoritative foreign-key definitions and optionality constraints, see `database.py`.

## 5. Dataset Record Counts

| Entity | Synthetic Records |
|---|---:|
| Requesters | 500 |
| Tickets | 5,000 |
| Policy Documents | 200 |
| Knowledge Articles | 200 |
| Messages | 20,000 |
| Assignments | 5,000 |
| SLA Records | 5,000 |
| Resolution Feedback | 4,034 |
| Ticket Events | 10,294 |
| Policy Citations | 4,706 |

These counts describe the generated baseline dataset.

## 6. Data Generation

The dataset is generated using:

`python generate_data.py`

Fixed random seed:

`20261022`

The generator creates related records so that tickets, messages, assignments, SLA records, and resolution outcomes can be checked together.

The generator is intended to produce reproducible results.

## 7. Data Integrity Rules

CampusResolve validates the generated dataset using the following checks:

1. Required record counts match expected totals.
2. Primary-key values are unique.
3. Foreign-key references are valid.
4. Ticket statuses belong to the allowed lifecycle states.
5. Ticket and event timestamps are chronologically consistent.
6. Policy effective dates are checked.
7. SLA calculations respect business hours.
8. Team assignments follow authorized routing rules.
9. Duplicate-record conditions are checked.
10. Ticket activity history is present.
11. Lifecycle and resolution records are checked for consistency.

The validation scripts are:

- `validate_dataset.py`
- `validate_lifecycle.py`
- `validate_negative_cases.py`
- `test_reproducibility.py`

## 8. Negative Test Dataset

Five intentional faults are injected into a separate copy of the baseline database.

| Case ID | Negative Scenario |
|---|---|
| NEG-001 | Expired policy citation |
| NEG-002 | Unauthorized routing |
| NEG-003 | Unsupported automated answer |
| NEG-004 | Incorrect business-hours SLA |
| NEG-005 | Missed escalation |

The expected labels are stored separately in `ground_truth.csv`.

The scenario-specific validation report is generated in `negative_validation_report.csv`.

All five injected scenarios were detected in the latest local validation run.

## 9. Reproducibility and Exports

The project includes:

- A deterministic dataset generator.
- A fixed random seed.
- A reproducibility test comparing independently generated datasets.
- CSV and JSON exports for selected tables.
- An SQL export.
- An export manifest containing row counts and checksums.

Run the export script with:

`python export_data.py`

## 10. Notes

This document summarizes the implemented database structure and its major relationships.

For exact SQL column types, primary keys, foreign keys, nullable fields, default values, and unique constraints, **`database.py` is the authoritative schema definition**.

The synthetic records are simulated campus support data, not real student or faculty records.