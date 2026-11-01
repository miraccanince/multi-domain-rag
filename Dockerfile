FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml lists the whole project as a package, so the source has to be
# present before installing it; the separate dependency-only caching layer that
# requirements.txt allowed is no longer possible this way.
COPY . .
# chroma-hnswlib builds with -march=native by default, which can crash on other CPUs.
ENV HNSWLIB_NO_NATIVE=1
RUN pip install --no-cache-dir .

# 8000: FastAPI, 8501: Streamlit
EXPOSE 8000 8501

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
