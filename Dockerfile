FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml lists the whole project as a package, so the source has to be
# present before installing it; the separate dependency-only caching layer that
# requirements.txt allowed is no longer possible this way.
COPY . .
RUN pip install --no-cache-dir .

# 8000: FastAPI, 8501: Streamlit
EXPOSE 8000 8501

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
