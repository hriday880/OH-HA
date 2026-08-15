# syntax=docker/dockerfile:1
# ==============================================================================
# Stage 1: Builder Stage
# Builds virtual environment and compiles wheels in an isolated builder container
# ==============================================================================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install minimal build tools for compiling C extensions if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install production Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: Runtime Stage
# Hardened, lightweight production image running under unprivileged non-root UID
# ==============================================================================
FROM python:3.11-slim-bookworm AS runner

# Container environment optimizations
# MALLOC_ARENA_MAX=2 prevents heap fragmentation in low-memory (256MB-512MB) containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    HOST=0.0.0.0 \
    VAULT_PATH=/app/vault \
    ENVIRONMENT=production \
    HOME=/home/botuser

# Install essential runtime utilities:
# - git: for bidirectional Obsidian vault synchronization
# - tini: lightweight PID 1 init to handle signals (SIGTERM/SIGINT) and reap zombies
# - openssh-client: for SSH deploy key authentication
# - ca-certificates: for secure HTTPS/TLS requests
# - curl: for healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    tini \
    openssh-client \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated unprivileged non-root user (UID 10001)
RUN groupadd -g 10001 botuser && \
    useradd -u 10001 -g botuser -s /bin/bash -m -d /home/botuser botuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Prepare application and vault working directories
WORKDIR /app
RUN mkdir -p /app/vault /app/deploy /home/botuser/.ssh && \
    chown -R botuser:botuser /app /home/botuser && \
    chmod 700 /home/botuser/.ssh

# Copy application source code and deployment entrypoint
COPY --chown=botuser:botuser bot/ /app/bot/
COPY --chown=botuser:botuser deploy/ /app/deploy/

# Ensure entrypoint is executable
RUN chmod +x /app/deploy/entrypoint.sh

# Switch to non-root user for security
USER botuser

# Expose keepalive HTTP health server port
EXPOSE 8080

# Built-in HEALTHCHECK probe querying the keepalive HTTP /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8080}/health || exit 1

# Execute tini as PID 1 init process wrapping entrypoint startup script
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]
CMD ["python", "-m", "bot.main"]
