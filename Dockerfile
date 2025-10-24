FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install Poetry
RUN pip install poetry

# Configure Poetry
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev

# Copy application code
COPY src/ ./src/
COPY conductor.proto ./

# Generate gRPC code
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. conductor.proto

# Create data directory
RUN mkdir -p /data

# Create keys directory
RUN mkdir -p /keys

# Create non-root user
RUN useradd -m -u 1000 conductor && \
    chown -R conductor:conductor /app /data /keys

USER conductor

# Expose ports
EXPOSE 4001 50051 9090 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the application
CMD ["python", "-m", "conductor.main"]
