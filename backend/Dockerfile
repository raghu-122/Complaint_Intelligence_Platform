FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure the data directories exist
RUN mkdir -p data/baseline/csv data/baseline/json data/baseline/sql data/anomalies

# Expose port
EXPOSE 8000

# Default: generate full-scale data then start server
CMD ["sh", "-c", "python cli.py generate --scale full --seed 20261022 --clear --export && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
