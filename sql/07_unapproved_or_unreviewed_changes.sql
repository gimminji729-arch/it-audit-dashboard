-- Control Test 7: Unapproved / Unreviewed Change Deployment
-- Risk: Changes pushed to production without prior approval, or
--       emergency changes never subjected to independent
--       post-implementation review, can introduce errors, fraud,
--       or unauthorized functionality without detection
-- Control: All changes require documented approval before
--          deployment; emergency changes require a post-hoc
--          independent review (ITGC - Program Change Management)
-- Logic: Flag a change request if any of the following hold:
--   (a) no approver is on record
--   (b) the deployment date precedes the approval date
--   (c) it is an emergency change with no reviewer on record

SELECT
    change_id,
    system,
    description,
    developer,
    approved_by,
    reviewed_by,
    approval_date,
    deployment_date,
    emergency_change,
    CASE
        WHEN approved_by IS NULL OR TRIM(approved_by) = '' THEN 'No approval on record before deployment'
        WHEN deployment_date < approval_date THEN 'Deployed to production before approval was recorded'
        WHEN emergency_change = 'Y' AND (reviewed_by IS NULL OR TRIM(reviewed_by) = '')
            THEN 'Emergency change with no independent post-implementation review'
        ELSE 'Other'
    END AS exception_reason
FROM change_requests
WHERE approved_by IS NULL
   OR TRIM(approved_by) = ''
   OR deployment_date < approval_date
   OR (emergency_change = 'Y' AND (reviewed_by IS NULL OR TRIM(reviewed_by) = ''))
ORDER BY deployment_date;
