-- Control Test 2: Dormant Account
-- Risk: An unused active account is a target for compromise/misuse
--       since activity on it is less likely to be noticed
-- Control: Accounts unused for 90+ days are automatically disabled
--          pending owner confirmation (ITGC - Access to Programs and Data)
-- Logic: Account is Active AND last login is more than 90 days before
--        the audit "as-of" date

SELECT
    ua.user_id       AS user_id,
    e.name           AS employee_name,
    e.department     AS department,
    e.job_title      AS job_title,
    ua.system        AS system,
    ua.account_status AS account_status,
    ua.last_login    AS last_login,
    CAST(julianday(:as_of_date) - julianday(ua.last_login) AS INTEGER) AS days_since_last_login
FROM user_accounts ua
JOIN employees e ON ua.employee_id = e.employee_id
WHERE ua.account_status = 'Active'
  AND julianday(:as_of_date) - julianday(ua.last_login) > 90
ORDER BY days_since_last_login DESC;
