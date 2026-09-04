FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PORT=8000

# Install system fonts and curl for TrueType typography & healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-carlito \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and data directory
COPY src/ ./src/
COPY data/ ./data/
COPY pyproject.toml .

EXPOSE 8000

# Start Football Remote Desk Server
CMD ["python", "-m", "src.cli", "serve"]
