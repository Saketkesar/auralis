# AURALIS VISION — web + CPU worker image.
# Used by the `web` and `celery-cpu` services in docker-compose.yml.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for image/forensics libraries and DB drivers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt gunicorn

COPY . .

# Run as a non-root user; stored bytes are never executed (24.4).
RUN useradd --create-home --uid 10001 auralis \
    && chown -R auralis:auralis /app
USER auralis

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:create_app()"]
