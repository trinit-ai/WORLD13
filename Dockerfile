FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY engine/pyproject.toml engine/pyproject.toml
RUN pip install --no-cache-dir "./engine"

# Copy source
COPY engine/ engine/
COPY protocols/ protocols/
COPY config/ config/

# Create directories — Railway volume will mount over vault/
# output/ stays ephemeral (deliverables are transient)
RUN mkdir -p vault output && chmod 777 vault output

WORKDIR /app/engine

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
