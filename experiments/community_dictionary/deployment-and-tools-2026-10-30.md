# Supervised deployment rehearsal and Tools navigation

Date: 30 October 2026. Base application commit:
`db1557ce1ae4f19245624a48a04d7aafb8c857cb`.

## Established deployment evidence

The private control workflow successfully installed the base commit on Manny's
Windows laptop. Manny browsed the result and accepted it. The AWS workflow then
verified that laptop receipt and installed the same commit through GitHub OIDC and
the fixed SSM document. The assistant inspected the successful workflow logs and
downloaded the AWS receipt: target `aws`, status `installed`, matching current and
previous application commits, and all 21 recorded steps successful, including service
shutdown, static collection and service restart. Manny independently reports normal
AWS browsing. This was a same-version rehearsal, not yet a changed-release trial.

Earlier AWS submissions failed with `InvalidDocument`; CloudTrail and the empty
command list established that they had not started deployment. The fixed document
was absent in the deployment region. Creating it in that region resolved the error.
The generic `control_api_call_failed` report obscured the cause; clearer safe error
reporting remains a separate controller improvement, outside this application change.

## Next visible change

Manny requests moving batch operations out of Settings. The prepared Tools tab is
owner-only and moves the existing four panels without changing their task URLs,
processing or approvals. Settings retains configuration and image style. Navigation,
return links and four new strings cover English, French and Slovak.

Focused verification: 85 Django tests pass across settings/pictures, batch
descriptions, capture vocabulary, localisation and public browsing. Existing tests
now cover Tools grouping, direct access restrictions, read-only GET, task return
links, active-tab context and translated labels. The first broader test attempt
found two missing resources in the fresh local inspection checkout; restoring the
unchanged repository resources resolved both errors. The full 728-test Community Dictionaries suite also passes. No provider calls were made.

Live laptop/AWS acceptance of Tools is pending. Automated functional acceptance,
AWS staging and sustained autonomous maintenance are not established by the
same-version deployment rehearsal. New code still follows laptop human acceptance
before production; schema/dependency/controller changes remain separate.
