# Small official Python image
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (Docker caches this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (templates, static files, python files)
COPY . .

EXPOSE 5000

# Run with gunicorn (production-style server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "90", "app:app"]
