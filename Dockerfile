FROM python:3.12-slim-bookworm

# Set the working directory
WORKDIR /app

COPY pyproject.toml ./

RUN mkdir -p stac_search

RUN pip install --no-cache-dir .

COPY stac_search/ ./stac_search/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI app
CMD ["uvicorn", "stac_search.api:app", "--host", "0.0.0.0", "--port", "8000"]