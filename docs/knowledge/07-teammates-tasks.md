# Orqentra guide · AI teammates, tasks and reviews
In Teammates, authorized users create and edit bounded AI teammate drafts. OWNER/ADMIN can publish immutable versions, inspect version history and archive definitions. A configured provider and an explicitly enabled organization worker are required to execute development tasks.

Tasks & reviews accepts task intake, shows queued/running results and supports clarification, cancellation and review. The worker uses published configuration and approved workspace knowledge. Intake is idempotent, claims use leases/fencing and retries are bounded. Approval is bound to the generated artifact revision and expiry; it is not blanket permission for arbitrary future actions.

Approved task outcomes currently create immutable SIMULATED delivery receipts. Orqentra does not actually send email, update a CRM or publish social posts. Chat likewise answers questions and does not execute arbitrary tools. An AI teammate definition is different from a human member and from a fictional demo profile. External integrations, arbitrary tool execution and a workflow editor remain future work.
