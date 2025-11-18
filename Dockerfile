FROM node:20 AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
EXPOSE 8000

# Install system dependencies for OCR (keep minimal in dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Prepare log directory
RUN mkdir -p /var/log/app && \
    chown -R root:root /var/log/app && \
    chmod 755 /var/log/app

# Copy requirements first so pip layer can be cached
COPY requirements.txt ./

# Use BuildKit cache for pip to speed repeated builds
# Requires BuildKit: DOCKER_BUILDKIT=1
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --default-timeout=120 -r requirements.txt

# Copy application code
COPY . .
COPY --from=frontend-build /workspace/frontend/dist ./app/static

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]