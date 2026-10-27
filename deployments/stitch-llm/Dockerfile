FROM python:3.12-slim-trixie AS base

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1

COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /uvx /bin/

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package stitch-llm

FROM base AS runtime

RUN groupadd --system --gid 999 stitch-app \
 && useradd --system --gid 999 --uid 999 --create-home stitch-app

COPY ./deployments /app/deployments
COPY ./packages /app/packages

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --package stitch-llm

ENV PATH="/app/.venv/bin:$PATH"
USER stitch-app

CMD ["uvicorn", "stitch.llm.main:app", "--host", "0.0.0.0", "--port", "8000"]
