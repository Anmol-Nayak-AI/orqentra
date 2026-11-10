"""Generate ignored local infrastructure configuration; never overwrite existing values."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
content = (
    "# Generated LOCAL DEVELOPMENT credentials; never use in production.\n"
    "POSTGRES_USER=orqentra_local_owner\nPOSTGRES_DB=orqentra\n"
    f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n"
    "POSTGRES_PORT=5432\nWEB_PORT=8080\n"
)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print("Existing .env preserved.")
else:
    with os.fdopen(fd, "w") as handle:
        handle.write(content)
    print("Created ignored .env with generated local credentials (mode 0600).")
