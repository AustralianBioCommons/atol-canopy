FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Ensure uv installs into a local virtual environment for the project
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies using the lockfile for reproducibility.
# Include README and app source so the editable build can resolve metadata.
COPY pyproject.toml uv.lock README.md ./
COPY app app
RUN uv sync --frozen --no-dev

# Copy the rest of the repository
COPY . .
RUN chmod +x scripts/entrypoint.sh

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Run migrations then start the FastAPI app via uv (respects the lockfile)
CMD ["./scripts/entrypoint.sh"]
