# AI Usage Disclosure — CampusResolve

## Project Overview

**Project:** CampusResolve — Student & Faculty Support Management System  
**Challenge:** YottaFlex.ai Coding Challenge  
**Technology:** Python, Flask, SQLite, HTML, CSS, and JavaScript

## AI Tools Used

ChatGPT (OpenAI) was used extensively as a development assistant throughout the project.

## How AI Assisted

AI assistance included:

- Planning the project architecture and database structure.
- Developing Python modules for ticket routing, policy-grounded responses, SLA calculations, and escalation workflows.
- Building the Flask application and frontend pages.
- Creating scripts for deterministic synthetic data generation, negative-case injection, and dataset exports.
- Developing automated tests and validation scripts.
- Drafting technical documentation, the data dictionary, and submission materials.
- Providing step-by-step debugging and GitHub setup guidance.

## Human Involvement and Validation

The developer worked in VS Code, executed the application and scripts, reviewed terminal results, and reported errors for correction.

Validation performed during development included:

- Generating 5,000 synthetic tickets and 20,000 messages.
- Exporting all 15 database tables to CSV and JSON, along with a SQL dump.
- Checking five intentionally injected negative cases.
- Running the automated test suite, with all eight test groups passing.
- Verifying the Flask application through browser testing.

These checks demonstrate the reported development results, but they do not establish that the system is production-ready.

## AI Prompt History

A separate file, `CampusResolve_AI_Prompt_History.pdf`, documents the project's AI-assisted workflow.

Where prompts have been rewritten or reconstructed for readability, they should not be treated as verbatim conversation transcripts. The original ChatGPT conversation history is the authoritative record of exact prompts.

## Limitations

- The dataset is synthetic rather than real university support data.
- Policy documents and knowledge articles are illustrative, not official institutional policies.
- Negative-case validation uses predefined scenarios and does not prove general detection of all possible failures.
- Additional security, performance, and real-world integration testing would be necessary before production deployment.

## Disclosure Statement

CampusResolve was developed with substantial AI-generated code and documentation assistance. The developer participated in project setup, execution, debugging, validation, and submission preparation. AI-generated outputs were not independently verified beyond the checks described above.
