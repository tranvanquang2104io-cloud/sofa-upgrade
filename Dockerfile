# ── Build stage: install Python dependencies ────────────────────────
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# System packages needed to compile psycopg and reportlab C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-warn-script-location \
        -r requirements.txt \
        gunicorn==21.2.0


# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

# Runtime-only system libraries:
#   libpq5           — psycopg
#   libreoffice-writer — DOCX→PDF conversion (soffice --headless) so the
#                        "in ra PDF" option produces a real PDF, not a DOCX fallback
#   fonts-liberation — Times New Roman-metric font with full Vietnamese coverage
#   fonts-dejavu-core — reportlab fallback / broad glyph coverage
#   ttf-mscorefonts-installer — REAL Times New Roman so DOCX→PDF renders the exact
#     DN-standard font (not the Liberation/DejaVu substitute mix that caused
#     inconsistent Vietnamese glyphs / "lỗi font khi in"). Needs contrib + EULA.
RUN sed -i 's/Components: main/Components: main contrib/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libfontconfig1 \
        fonts-dejavu-core \
        fonts-liberation \
        libreoffice-writer \
        cabextract \
        wget \
    && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y ttf-mscorefonts-installer \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security
RUN useradd -m -u 1001 appuser
WORKDIR /app
RUN chown appuser:appuser /app

# Copy application source
COPY --chown=appuser:appuser . .

# Upload directories must exist inside container; actual data lives in volumes
RUN mkdir -p app/uploads/documents app/uploads/templates app/uploads/items \
 && chown -R appuser:appuser app/uploads \
 && sed -i 's/\r$//' entrypoint.sh \
 && chmod +x entrypoint.sh

USER appuser

# Expose port (Gunicorn listens here; Nginx proxies to it)
EXPOSE 5000

# Entrypoint: khởi tạo DB/master admin rồi mới chạy app
ENTRYPOINT ["/app/entrypoint.sh"]

# Default: run Gunicorn with 4 workers
# Override CMD in docker-compose for dev (flask run with reload)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "60", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]
