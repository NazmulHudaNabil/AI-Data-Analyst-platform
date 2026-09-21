# Use the official Python slim image for a smaller footprint
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install system dependencies required for psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies using standard pip
# (The requirements.txt was pre-compiled via 'uv' for speed and determinism)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the API port (for local development)
EXPOSE 8000

# Start the FastAPI application using uvicorn
# Use ${PORT:-8000} to allow Heroku to dynamically assign the port, while defaulting to 8000 locally
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
