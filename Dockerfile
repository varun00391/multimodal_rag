FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# OpenCV (Docling TableFormer) needs X11/GL libraries that slim does not ship.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libxcb1 \
        libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

RUN mkdir -p /app/output /app/data

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
