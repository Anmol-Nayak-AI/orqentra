"""Reserve an explicit demo seeding entrypoint without bypassing future migrations/auth."""

import sys

sys.exit(
    "No demo data was written. Checkpoint 2B schema exists; "
    "Implement explicit demo fixtures after trusted identity and authorization in 2C."
)
