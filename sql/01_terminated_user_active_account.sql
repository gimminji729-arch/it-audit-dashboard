-- Control Test 1: Terminated User With Active Account
-- Risk: Unauthorized post-termination access to company systems
-- Control: HR termination data is compared to IT account status on a
--          recurring basis and access is revoked within 24 hours of
--          separation (ITGC - Access to Programs and Data)
-- Logic: Employee status = Terminated AND the linked system account
--        is still Active

SELECT
    ua.user_id            AS user_id,
    e.employee_id         AS employee_id,
    e.name                AS employee_name,
    e.department           AS department,
    e.job_title            AS job_title,
    ua.system              AS system,
    ua.account_status      AS account_status,
    e.termination_date     AS termination_date,
    ua.last_login          AS last_login
FROM user_accounts ua
JOIN employees e ON ua.employee_id = e.employee_id
WHERE e.status = 'Terminated'
  AND ua.account_status = 'Active'
ORDER BY e.termination_date;
