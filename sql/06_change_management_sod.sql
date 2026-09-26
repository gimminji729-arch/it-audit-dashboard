-- Control Test 6: Change Management SoD Conflict (Developer = Approver)
-- Risk: A developer who approves their own code change can push
--       unauthorized or untested logic into production undetected
-- Control: Program changes must be approved by someone other than
--          the developer before deployment
--          (ITGC - Program Change Management)
-- Logic: The "Developer" and "Approved By" fields on the same
--        change request are the same person

SELECT
    change_id,
    system,
    description,
    developer,
    approved_by,
    approval_date,
    deployment_date
FROM change_requests
WHERE developer IS NOT NULL
  AND approved_by IS NOT NULL
  AND developer = approved_by
ORDER BY deployment_date;
