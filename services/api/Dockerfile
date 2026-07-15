FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system aegisops && adduser --system --ingroup aegisops aegisops

COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/api/README.md services/api/README.md
COPY services/api/src services/api/src
COPY services/api/alembic.ini services/api/alembic.ini
COPY services/api/alembic services/api/alembic
COPY configs configs
COPY policies policies

RUN python -m pip install --upgrade pip \
    && python -m pip install ./services/api

USER aegisops

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn aegisops_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
