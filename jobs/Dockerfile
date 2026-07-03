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

# Copy crawler, configurations, and crawler utility folders
COPY agent/ /app/agent/
COPY jobs/ /app/jobs/
COPY utility/ /app/utility/

# Set Python search paths to resolve utility.* and src.* imports
ENV PYTHONPATH=/app:/app/agent

CMD ["python", "jobs/worker.py"]
