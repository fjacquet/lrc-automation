FROM python:3.12-slim

LABEL org.opencontainers.image.title="lrc-automation" \
      org.opencontainers.image.description="Lightroom Classic catalog automation — scan, plan, apply, validate, reconcile" \
      org.opencontainers.image.source="https://github.com/fjacquet/lrc-automation" \
      org.opencontainers.image.licenses="MIT"

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install the package (no geo extra — reverse_geocoder has no Linux wheel in CI)
RUN uv pip install --system --no-cache ".[geo]" 2>/dev/null || uv pip install --system --no-cache .

# Catalog is mounted at /catalog by convention
# Usage: docker run --rm -v /path/to/lightroom:/catalog ghcr.io/fjacquet/lrc-automation scan -c /catalog/Catalog.lrcat
ENTRYPOINT ["lrc-auto"]
CMD ["--help"]
