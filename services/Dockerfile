# syntax=docker/dockerfile:1
# Shared `deps` stage is built once and reused by every service.
# Extraction uses target `extraction` so it is the only image that installs Docling.
#
# Do not use FROM ${VAR}: Compose bake passes empty build-args for unused
# ARGs, which overrides Dockerfile defaults and yields a blank base name.

FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/shared \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY multimodal_rag_app/shared/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

FROM deps AS with-docling

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY multimodal_rag_app/shared/requirements-extraction.txt ./requirements-extraction.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-extraction.txt

FROM deps AS runtime

ARG SERVICE_DIR
ARG SERVICE_PORT=8000
ENV PORT=${SERVICE_PORT}

COPY rag ./rag
COPY multimodal_rag_app/shared ./shared
COPY ${SERVICE_DIR} ./service

RUN mkdir -p /data/uploads/workspaces

WORKDIR /app/service
EXPOSE ${SERVICE_PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}

FROM with-docling AS extraction

ARG SERVICE_DIR
ARG SERVICE_PORT=8010
ENV PORT=${SERVICE_PORT}

COPY rag ./rag
COPY multimodal_rag_app/shared ./shared
COPY ${SERVICE_DIR} ./service

RUN mkdir -p /data/uploads/workspaces

WORKDIR /app/service
EXPOSE ${SERVICE_PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
