USE it_ticketing_system;

-- JOIN: ticket, employee and category
SELECT t.ticket_id, t.title, u.name AS employee, c.category_name
FROM tickets t
INNER JOIN users u ON u.user_id=t.user_id
INNER JOIN categories c ON c.category_id=t.category_id;

-- LEFT JOIN: show unassigned tickets too
SELECT t.ticket_id, t.title, requester.name AS employee, staff.name AS assigned_staff
FROM tickets t
JOIN users requester ON requester.user_id=t.user_id
LEFT JOIN users staff ON staff.user_id=t.assigned_to;

-- Aggregate functions
SELECT COUNT(*) AS total_tickets,
       SUM(status='Open') AS open_tickets,
       MAX(created_at) AS latest_ticket
FROM tickets;

-- GROUP BY and HAVING
SELECT assigned_to, COUNT(*) AS assigned_count
FROM tickets
WHERE assigned_to IS NOT NULL
GROUP BY assigned_to
HAVING COUNT(*) >= 1;

-- Nested subquery: employees with above-average ticket volume
SELECT u.user_id, u.name, COUNT(t.ticket_id) AS ticket_count
FROM users u JOIN tickets t ON t.user_id=u.user_id
WHERE u.role='Employee'
GROUP BY u.user_id, u.name
HAVING COUNT(t.ticket_id) > (
    SELECT AVG(ticket_count)
    FROM (SELECT COUNT(*) AS ticket_count FROM tickets GROUP BY user_id) AS counts_by_employee
);

-- EXISTS subquery
SELECT u.user_id, u.name
FROM users u
WHERE u.role='Employee'
AND EXISTS (SELECT 1 FROM tickets t WHERE t.user_id=u.user_id);

-- View: reusable ticket status summary
CREATE OR REPLACE VIEW vw_ticket_status_summary AS
SELECT status, COUNT(*) AS total_tickets
FROM tickets GROUP BY status;

SELECT * FROM vw_ticket_status_summary;