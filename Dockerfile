FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8501

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[app]"

COPY app ./app
COPY .streamlit ./.streamlit

USER app
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health', timeout=4)" || exit 1

# PORT is honoured so the same image runs on Cloud Run, Render, Fly.io and Hugging Face Spaces.
CMD ["sh", "-c", "streamlit run app/streamlit_app.py --server.port=${PORT} --server.address=0.0.0.0"]
