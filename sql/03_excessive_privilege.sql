-- Control Test 3: Excessive Privilege (Least Privilege violation)
-- Risk: Unapproved system changes or data access by staff outside
--       the function that role was designed for
-- Control: Administrative roles are restricted to IT/system-owner staff
--          and reviewed quarterly against least-privilege principle
--          (ITGC - Access to Programs and Data)
-- Logic: User holds a role containing "Admin" and either
--        (a) their department does not match the system's admin
--            function, or
--        (b) the account has no corresponding employee record at all
--            (ownership cannot be verified, so it cannot be judged
--             appropriate and is flagged by default)

SELECT
    ur.user_id        AS user_id,
    ua.employee_id    AS employee_id,
    e.name            AS employee_name,
    e.department      AS department,
    e.job_title       AS job_title,
    ur.role           AS role,
    ur.system         AS system
FROM user_roles ur
JOIN user_accounts ua ON ur.user_id = ua.user_id
LEFT JOIN employees e ON ua.employee_id = e.employee_id
WHERE ur.role LIKE '%Admin%'
  AND (
        e.employee_id IS NULL
        OR (ur.role = 'SAP System Admin' AND e.department <> 'Information Technology')
        OR (ur.role = 'IAM Admin'        AND e.department <> 'Information Technology')
        OR (ur.role = 'Payroll Admin'    AND e.department <> 'Human Resources')
      )
ORDER BY department;
