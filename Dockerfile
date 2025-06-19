FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock ./

COPY stac_search/ ./stac_search/

RUN uv sync --frozen

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI app
CMD ["uv", "run", "uvicorn", "stac_search.api:app", "--host", "0.0.0.0", "--port", "8000"]