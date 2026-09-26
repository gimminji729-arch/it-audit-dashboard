-- Control Test 4: Segregation of Duties (SoD) Conflict
-- Risk: One person can both initiate and approve the same
--       transaction end-to-end, enabling fraud or error to go
--       undetected
-- Control: Conflicting roles are assigned to different employees;
--          any exception requires a documented compensating control
--          (ITGC - Access to Programs and Data)
-- Logic: A single user holds both roles of a pair defined in the
--        SoD rule library (sod_rules), within the same system

SELECT
    a.user_id           AS user_id,
    ua.employee_id       AS employee_id,
    e.name               AS employee_name,
    e.department         AS department,
    r.role_1             AS conflicting_role_1,
    r.role_2             AS conflicting_role_2,
    r.risk_description   AS risk_description,
    a.system             AS system
FROM user_roles a
JOIN user_roles b
    ON a.user_id = b.user_id
   AND a.system  = b.system
   AND a.role   <> b.role
JOIN sod_rules r
    ON r.role_1 = a.role
   AND r.role_2 = b.role
   AND r.system = a.system
LEFT JOIN user_accounts ua ON a.user_id = ua.user_id
LEFT JOIN employees e ON ua.employee_id = e.employee_id
ORDER BY a.user_id;
