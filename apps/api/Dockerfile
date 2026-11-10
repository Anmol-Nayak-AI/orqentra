FROM astral/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv
FROM python:3.12.15-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" \
    ORQENTRA_ENVIRONMENT=production
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/alembic apps/api/alembic
RUN uv sync --locked --no-dev --package orqentra-api --no-editable \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; host=os.environ.get('ORQENTRA_ALLOWED_HOSTS','127.0.0.1').split(',')[0].strip(); req=urllib.request.Request('http://127.0.0.1:8000/api/v1/health',headers={'Host':host}); urllib.request.urlopen(req,timeout=3)"]
CMD ["uvicorn", "orqentra.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
