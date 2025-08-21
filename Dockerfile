FROM python:3.12-slim
WORKDIR /app
EXPOSE 8000

# Install system dependencies for OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-por \
    tesseract-ocr-spa \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*
# Prepare log directory
RUN mkdir -p /var/log/app && \
    chown -R root:root /var/log/app && \
    chmod 755 /var/log/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
