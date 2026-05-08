# X12 And API Remit Workflow Alignment

This proof package is vendor-neutral, but it is designed around the same kind of clearinghouse/API surface described in public Medical Network API documentation such as Optum/Change Healthcare-style eligibility, claims, claim-status, reports, and remittance workflows.

It does not claim a vendor relationship, production certification, or live connection.

## Where This Repo Fits

| Upstream surface | Transaction or file | Repo responsibility |
| --- | --- | --- |
| Claims submission | `837P` or `837I` | Receives the submitted claim identifier needed for later remit matchback. |
| Acknowledgment tracking | `999` and `277CA` | Keeps rejected or accepted claim paths separate before payment work begins. |
| Claim status | `276/277` | Provides follow-up context when a claim is accepted but payment has not arrived. |
| Reports/remittance retrieval | `835 ERA` or ERA mailbox/report endpoint | Normalizes paid, denied, adjusted, and patient-responsibility lines. |
| Posting and follow-up | CARC/RARC from `835` | Routes variance, denial, documentation, authorization, medical necessity, and posting queues. |

## Public Safety Language

Safe wording:

> RevCycleMGMT can build remit and denial workflows that prepare teams for clearinghouse/API reporting and remittance endpoints using synthetic test files before production onboarding.

Unsafe wording unless formally true:

> RevCycleMGMT is certified by a clearinghouse vendor.

> RevCycleMGMT has a live production vendor connection.

> RevCycleMGMT guarantees payment or payer acceptance.

## Demo Boundary

The `output_demo/835_preview.edi` artifact is an educational synthetic X12-style preview. It is useful for explaining the operating workflow, but production onboarding would still require payer-specific companion guides, secure transport, credential management, posting-rule review, and client approval.
