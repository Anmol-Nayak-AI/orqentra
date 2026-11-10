# Orqentra guide — Workspaces, Python analysis and code approval

As of 10 November 2026, Organization Settings lets OWNER and ADMIN members create and rename workspaces. Use a workspace in Knowledge, Teammates and Chat. Workspaces share organization membership permissions; they are not separate per-person access groups.

For AI-generated Python, create a teammate, choose Python analysis proposal, add instructions and publish its saved version. Add approved source text to its workspace. In Tasks & reviews, select that published version and submit the analysis request. The AI prepares a grounded plan and proposed_python code. Nothing executes during generation. Review the evidence and approve the task; an approved artifact can be downloaded as a text file.

After task approval, its proposed Python appears in the code proposal form. Submit it for independent code review. A different active OWNER or ADMIN must approve the exact code hash. Code approval expires after one hour. A task approval alone is never authorization to execute code.

Run in isolated sandbox is available only when an operator has explicitly authorized and configured a healthy E2B worker. Default development configuration keeps E2B execution disabled. Backend keys never belong in chat or source documents. Execution has network, time and output limits and runs outside the API and worker containers. UNKNOWN means remote execution could not be confirmed and will not retry automatically. No production readiness or paid-resource approval is implied by these features.

If AI processing is unavailable, an operator must activate the worker for the organization. Existing conversations and human support remain available. The product does not silently start paid resources for new organizations.
