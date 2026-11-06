# IT Ticketing Support System

A role-based IT helpdesk application built with **Python, Streamlit and MySQL**. Employees can report technical issues, IT staff can manage and resolve tickets, and administrators can monitor support operations.

## Features

### Employee
- Register and sign in securely.
- Create tickets with a category, priority and description.
- View, search, filter and track submitted tickets.
- Review assignment, target deadline, comments and activity history.

### IT Staff
- View assigned work and the shared ticket queue.
- Pick up unassigned tickets.
- Update ticket status and priority.
- Communicate through ticket comments and review ticket activity.

### Admin
- Monitor ticket volume, status, priority, overdue work and resolution performance.
- Search and manage all tickets, including assignments and target deadlines.
- Review team workload and user roles.
- Explore operational reports using SQL joins, aggregates, grouping and subqueries.

## Technology stack

- **Python** — application and business logic.
- **Streamlit** — web interface, forms, dashboards and navigation.
- **MySQL** — persistent relational data storage.
- **SQL** — CRUD operations, joins, aggregate functions, `GROUP BY`, `HAVING` and subqueries.
- **Pandas / Plotly** — query-result handling and interactive charts.
- **PBKDF2 password hashing** — password storage without saving plain-text passwords.

## Database design

The application initializes and upgrades its tables when it starts. First create the database by running `schema.sql` in MySQL Workbench.

The application uses these tables:

| Table | Purpose |
|---|---|
| `users` | Employee, IT Staff and Admin accounts |
| `categories` | Available issue categories |
| `tickets` | Issue details, requester, assignment, priority, status and deadlines |
| `comments` | Conversation messages attached to tickets |
| `ticket_events` | Activity history such as ticket creation, assignment and status changes |

Primary keys and foreign keys connect the records. A user can raise many tickets; a support user can be assigned many tickets; a ticket can have many comments and activity events.

## Requirements

- Python 3.10 or newer
- MySQL Server 8 or newer
- MySQL Workbench (recommended)
- VS Code or another Python IDE

## Setup (Windows PowerShell)

1. Clone the repository and open its folder:

   ```powershell
   git clone https://github.com/Vinithreddy6/IT-Ticketing-Support-System.git
   cd IT-Ticketing-Support-System
   ```

2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. In MySQL Workbench, run `schema.sql` to create the database.

5. Create your local Streamlit secrets file by copying `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then enter your own MySQL credentials:

   ```toml
   [mysql]
   host = "localhost"
   port = 3306
   user = "YOUR_MYSQL_USER"
   password = "YOUR_MYSQL_PASSWORD"
   database = "it_ticketing_system"
   ```

6. Start the app from the repository folder:

   ```powershell
   streamlit run app.py
   ```

   Streamlit will show a local URL, normally `http://localhost:8501`.

The application can also read connection settings from `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` and `MYSQL_DATABASE` environment variables.

## Demo accounts

The application seeds demo accounts when they are missing:

| Role | Email | Password |
|---|---|---|
| Employee | `employee@demo.com` | `Employee@123` |
| IT Staff | `itstaff@demo.com` | `ITStaff@123` |
| Admin | `admin@demo.com` | `Admin@123` |

These credentials are for local demonstration only. Change or remove demo accounts before exposing the application to a network or the internet.

## SQL practice files

- `mysql_advanced_queries.sql` — additional runnable SQL examples for MySQL Workbench.
- `MYSQL_CONCEPTS.md` — quick notes on the SQL concepts used in the project.

Run the examples only after selecting the `it_ticketing_system` database. Review each statement before executing it against a database containing important data.

## Security and deployment notes

- Do not commit `.streamlit/secrets.toml`, `.env`, passwords or other credentials. The repository includes only a placeholder secrets example.
- Use a least-privilege MySQL account instead of the root account.
- Remove demo accounts and rotate credentials before deployment.
- Add HTTPS, rate limiting, session hardening, backups and monitoring before production use.

This project is intended as a learning and demonstration application; it is not a production-hardened helpdesk service.
