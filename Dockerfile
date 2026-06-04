FROM python:3.12-slim

# System deps: libmagic (file detection), tesseract (OCR), poppler (PDF→image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
