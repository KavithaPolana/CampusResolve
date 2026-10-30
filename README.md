# CampusResolve
### Student & Faculty Support Management System

CampusResolve is a web-based support management system designed to manage student and faculty requests across campus departments. It provides automated ticket routing, policy-grounded support responses, business-hours SLA tracking, human escalation, and a traceable ticket history.

The project was developed for the **YottaFlex.ai Coding Challenge 2026**.

## 1. Project Overview

CampusResolve supports four major service categories:

- Financial Aid
- Registration
- IT Support
- Accessibility

The application provides a working Flask website for creating and tracking support requests, along with a separate deterministic synthetic dataset for analysis and validation.

## 2. Key Features

### Ticket Management
- Create student and faculty support tickets.
- Generate ticket identifiers using the `TKT-2026-000001` format.
- View tickets, statuses, requester details, and assigned teams.
- Search and filter tickets with pagination.
- Maintain a chronological activity history.

### Automated Routing
- Assign tickets to support teams using category-based routing rules.
- Check that assignments use authorized teams.
- Record routing decisions for traceability.

### Policy-Grounded Responses
- Retrieve relevant policy information.
- Include policy identifiers, versions, and effective dates.
- Avoid generating unsupported automated responses.
- Escalate requests requiring human review.

### SLA Management
- Calculate response and resolution deadlines.
- Apply business hours: Monday–Friday, 9:00 AM–5:00 PM IST.
- Track first responses and resolution timestamps.
- Monitor SLA deadlines and trigger escalation when required.

### Human Escalation
- Escalate requests when suitable policy guidance is unavailable.
- Support escalation for unresolved or overdue requests.
- Preserve escalation activity in ticket history.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Dataset Generation | Python |
| Automated Testing | Python |
| Data Exports | CSV, JSON, SQL |
| Version Control | Git and GitHub |

## 4. Synthetic Dataset

CampusResolve includes a deterministic synthetic dataset generated using the fixed random seed:

`20261022`

The dataset contains:

| Entity | Record Count |
|---|---:|
| Tickets | 5,000 |
| Knowledge Articles | 200 |
| Messages | 20,000 |
| Requesters | 500 |
| Policy Documents | 200 |
| Assignments | 5,000 |
| SLA Records | 5,000 |
| Resolution Feedback | 4,034 |
| Ticket Events | 10,294 |
| Policy Citations | 4,706 |

### Ticket Status Distribution

| Status | Tickets |
|---|---:|
| Resolved | 4,034 |
| In Progress | 672 |
| Escalated | 294 |
| **Total** | **5,000** |

The synthetic dataset covers Financial Aid, Registration, IT, and Accessibility requests.

It includes ambiguous questions, policy-related requests, deadlines, and escalation scenarios.

The generated dataset is stored in `synthetic_campusresolve.db`, separately from the live application database `campusresolve.db`.

## 5. Database Design

The application uses a relational SQLite database with 15 tables:

1. `roles`
2. `requesters`
3. `terms`
4. `categories`
5. `policy_documents`
6. `knowledge_articles`
7. `tickets`
8. `assignments`
9. `messages`
10. `sla`
11. `resolution_feedback`
12. `ticket_events`
13. `routing_rules`
14. `policy_citations`
15. `sla_business_hours`

The database includes primary keys, foreign keys, and relationships between requesters, tickets, policies, assignments, messages, and service-level agreements.

## 6. Negative Test Cases

Five intentional negative scenarios are included in a separate test database:

| Case | Description |
|---|---|
| NEG-001 | Expired policy citation |
| NEG-002 | Unauthorized team routing |
| NEG-003 | Unsupported automated answer |
| NEG-004 | SLA business-hours calculation error |
| NEG-005 | Missed escalation |

The negative dataset is stored in:

`synthetic_campusresolve_negative.db`

Expected labels are maintained separately in:

`ground_truth.csv`

The negative-case validation script checks these five injected scenarios and produces:

`negative_validation_report.csv`

**Result:** All 5 injected negative cases were detected by the scenario-specific checks.

## 7. Installation and Setup

### Requirements

- Python 3.10 or later, with compatible dependencies
- Git
- A modern web browser

### Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd CampusResolve
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the actual repository URL after publishing.

### Create a Virtual Environment

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

### Install Dependencies

```powershell
pip install Flask
```

### Generate the Synthetic Dataset

```powershell
python generate_data.py
```

### Generate Negative Cases

```powershell
python generate_negative_cases.py
```

### Run the Application

```powershell
python app.py
```

Open:

`http://127.0.0.1:5001`

## 8. Application Pages

### Dashboard
Displays synthetic dataset statistics, including ticket counts and category distribution.

### Create Ticket
Allows students and faculty to submit new support requests. Tickets are processed through routing, SLA creation, and policy-answer workflows.

### All Tickets
Displays the synthetic dataset with pagination, search, and status filters. A separate tab provides access to live tickets.

### Ticket Details
Displays the issue description, requester, assigned team, status, activity history, conversation, policy references, and SLA deadlines.

## 9. Dataset Validation

Run the baseline dataset validation:

```powershell
python validate_dataset.py
```

Run the negative-case checks:

```powershell
python validate_negative_cases.py
```

Run lifecycle consistency validation:

```powershell
python validate_lifecycle.py
```

Run reproducibility verification:

```powershell
python test_reproducibility.py
```

Run the complete automated test suite:

```powershell
python run_all_tests.py
```

### Latest Test Results

| Metric | Result |
|---|---|
| Test groups passed | 8/8 |
| Test groups failed | 0 |
| Baseline dataset validation | 11/11 checks passed |
| Injected negative cases detected | 5/5 |
| Lifecycle consistency | 0 errors, 0 warnings |
| Reproducibility | Passed |

These results describe the local tests executed during development.

## 10. Dataset Exports

Run:

```powershell
python export_data.py
```

The export process generates CSV and JSON files for selected database tables, an SQL database dump, and a checksum manifest.

The manifest records export file hashes and row counts to support verification.

## 11. Reproducibility

The dataset generator uses a fixed random seed (`20261022`) to make the synthetic data reproducible.

The reproducibility test regenerates the dataset in two separate temporary directories and compares logical dataset checksums and record counts.

## 12. Project Limitations

- CampusResolve is a local demonstration application, not a production-deployed campus service.
- Synthetic data represents simulated support activity rather than real student records.
- Policy responses are based on predefined policy records and rules, not a general-purpose AI chatbot.
- Negative-case checks are designed for the five injected scenarios; they do not establish detection accuracy for all possible unseen errors.
- Authentication and production-grade access control are not included in the current demonstration.

## 13. AI Assistance Disclosure

AI assistance was used during development for code drafting, debugging guidance, documentation, and test design. The implementation was reviewed and tested through local execution.

See `AI_DISCLOSURE.md` for additional details.

## 14. Conclusion

CampusResolve demonstrates an end-to-end student and faculty support workflow, combining automated routing, policy-grounded answers, business-hours SLA management, escalation, ticket traceability, and deterministic synthetic data generation.

The project includes a functional Flask interface, structured SQLite datasets, validation scripts, and automated tests to support review and reproducibility.