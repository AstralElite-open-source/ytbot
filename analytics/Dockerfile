FROM python:3.11-slim

WORKDIR /app

# Disable Python output buffering
ENV PYTHONUNBUFFERED=1

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all analytics scripts
COPY *.py .

# Default command (can be overridden)
CMD ["python", "-u", "simple_stats.py"]

