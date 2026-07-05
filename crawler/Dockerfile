FROM python:3.11-slim

# Install wget/curl to fetch playwright OS dependency packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and system-level OS dependencies for Chromium only
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy crawler and agent configurations
COPY agent/ /app/agent/
COPY crawler/ /app/crawler/

# Set Python search paths to resolve utility.* and src.* imports
ENV PYTHONPATH=/app:/app/agent

CMD ["python", "crawler/worker.py"]
