FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .[media]

RUN useradd --create-home --uid 1000 extraction \
    && mkdir -p /app/output /app/models/home \
    && chown -R extraction:extraction /app

USER extraction

ENV PYTHONPATH=/app/src \
    EXTRACTION_WORKSPACE=/app/output \
    EXTRACTION_MODEL_CACHE=/app/models \
    HOME=/app/models/home \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "extraction.app:app", "--host", "0.0.0.0", "--port", "8000"]
