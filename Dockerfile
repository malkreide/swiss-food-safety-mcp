# syntax=docker/dockerfile:1
# Multi-stage build — SEC-007 / SCALE-004

FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip build \
    && pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

# Run as an unprivileged user, never root.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER appuser
EXPOSE 8002

# Container deployment is the intended external-exposure case, so 0.0.0.0 is
# passed explicitly here (SEC-016) rather than relying on the loopback default.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,sys; s=socket.socket(); s.settimeout(3); \
sys.exit(0 if s.connect_ex(('127.0.0.1',8002))==0 else 1)"

CMD ["swiss-food-safety-mcp", "--http", "--host", "0.0.0.0"]
