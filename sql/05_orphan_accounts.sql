-- Control Test 5: Orphan Account
-- Risk: A live account with no verifiable owner in the HR master
--       cannot be attributed to anyone, so its activity and access
--       cannot be justified or monitored
-- Control: Every system account must map to a valid employee record
--          or an approved/documented service account
--          (ITGC - Access to Programs and Data)
-- Logic: The account's Employee ID does not exist in the employee
--        master file

SELECT
    ua.user_id      AS user_id,
    ua.employee_id  AS employee_id_on_account,
    ua.system       AS system,
    ua.account_status AS account_status,
    ua.last_login   AS last_login
FROM user_accounts ua
LEFT JOIN employees e ON ua.employee_id = e.employee_id
WHERE e.employee_id IS NULL
ORDER BY ua.system;
