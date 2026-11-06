# IT Ticketing Support System

A role-based IT helpdesk web application built with **Python, Streamlit, and MySQL**.

## Features

- Employee registration and login
- Secure password hashing with PBKDF2
- Create tickets with category, priority, and description
- Employees can view only their own tickets
- IT Staff/Admin can view the ticket queue
- Assign tickets to IT Staff/Admin
- Update priority and status
- Ticket comments / conversation history
- Dashboard metrics and status/category charts
- Parameterized SQL queries and relational foreign keys

## Requirements

- Python 3.10+
- MySQL Server 8+
- MySQL Workbench (recommended)
- VS Code or another Python IDE

## 1. Create the database

Open MySQL Workbench and run `schema.sql`.

Alternatively, run:

```sql
CREATE DATABASE it_ticketing_system;
```

The application creates the tables and default categories automatically at startup. The database itself must exist first.

## 2. Create and activate a virtual environment (recommended)

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install packages

```bash
pip install -r requirements.txt
```

## 4. Configure MySQL

Create `.streamlit/secrets.toml` by copying `.streamlit/secrets.toml.example`, then enter your own MySQL password:

```toml
[mysql]
host = "localhost"
port = 3306
user = "root"
password = "YOUR_MYSQL_PASSWORD"
database = "it_ticketing_system"
```

Do not commit `secrets.toml` or share your database password.

You can also set environment variables `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`.

## 5. Start the application

From the project folder:

```bash
streamlit run app.py
```

Streamlit will print a local URL, normally `http://localhost:8501`.

## 6. Demo accounts

Demo users and sample tickets are created automatically on first run if those email addresses do not already exist.

| Role | Email | Password |
|---|---|---|
| Employee | employee@demo.com | Employee@123 |
| IT Staff | itstaff@demo.com | ITStaff@123 |
| Admin | admin@demo.com | Admin@123 |

Use these only for local demonstration. Change/remove demo accounts before exposing the app to a network or the internet.

## Demo walkthrough

### Employee demo
1. Sign in as `employee@demo.com`.
2. Open **Create ticket**.
3. Submit a ticket such as “Laptop cannot connect to VPN”.
4. Open **My tickets** to see the ticket and its status.
5. Open the ticket, add a comment, and follow the conversation.

### IT Staff demo
1. Sign out and sign in as `itstaff@demo.com`.
2. Open **Ticket queue**.
3. Select a ticket from the list.
4. Change status to **In Progress** or **Resolved**.
5. Assign it to a support user and save changes.
6. Add a comment with the troubleshooting update.

### Admin demo
1. Sign in as `admin@demo.com`.
2. Review the ticket queue.
3. Open **Reports** to see status and category charts.
4. Manage assignment, priority, and ticket status.

## Project structure

```text
IT_Ticketing_System/
├── app.py
├── database.py
├── schema.sql
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── secrets.toml.example
```

## Database relationship overview

- One user can raise many tickets.
- One support user can be assigned many tickets.
- One category can contain many tickets.
- One ticket can have many comments.
- Every comment is written by one user.

## Important production notes

This is a learning/demo project, not a production-hardened service. Before production use:
- Use a least-privilege MySQL account rather than the root account.
- Use HTTPS and a production deployment platform.
- Add CSRF/session hardening, rate limiting, password reset, audit logs, and automated backups.
- Add stronger operational monitoring and access policies.
- Review data retention and privacy requirements.
- Remove demo accounts and rotate all credentials.