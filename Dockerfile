FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY prompts/ prompts/

# Create data directory
RUN mkdir -p data

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "-m", "src.main"]
