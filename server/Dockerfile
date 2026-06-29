# ──────────────────────────────────────────────
# Stage 1: Builder — Compile dependencies
# ──────────────────────────────────────────────
FROM python:3.13-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache gcc musl-dev postgresql-dev build-base libffi-dev

# Copy requirements and build wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ──────────────────────────────────────────────
# Stage 2: Runtime — Minimal production image
# ──────────────────────────────────────────────
FROM python:3.13-alpine AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apk add --no-cache postgresql-libs libffi

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy application
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]