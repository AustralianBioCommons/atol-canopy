FROM ghcr.io/astral-sh/uv:python3.10-slim

WORKDIR /app

# Ensure uv installs into a local virtual environment for the project
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies using the lockfile for reproducibility
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source
COPY app app
COPY scripts scripts
COPY schema.sql .
COPY README.md .
COPY .env.example .

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Run the FastAPI app via uv (respects the lockfile)
CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
