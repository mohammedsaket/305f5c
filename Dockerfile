FROM node:22-alpine AS web
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DAYMARK_ROOT=/app \
    PORT=8000
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 daymark
COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements-dev.txt
COPY backend /app/backend
COPY data/raw /app/data/raw
COPY --from=web /src/dist /app/static
WORKDIR /app/backend
RUN python -m daymark.build && python -m pytest -q
USER daymark
EXPOSE 8000
CMD ["sh", "-c", "uvicorn daymark.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
