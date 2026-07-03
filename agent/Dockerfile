FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source code
COPY agent/ /app/agent/

# Set Python search path to resolve src.* modules
ENV PYTHONPATH=/app/agent

CMD ["python", "agent/main.py"]
