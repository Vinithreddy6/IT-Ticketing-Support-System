# MySQL concepts included

The app uses relational tables (`users`, `categories`, `tickets`, `comments`) with primary
and foreign keys. The Reports page now executes live MySQL queries using INNER JOIN,
LEFT JOIN, COUNT, SUM, AVG, GROUP BY, HAVING, nested subqueries and conditional
aggregation. `mysql_advanced_queries.sql` contains additional runnable examples,
including EXISTS and a view.

Run the SQL examples in MySQL Workbench after selecting `it_ticketing_system`.
They do not drop the database or delete existing records.