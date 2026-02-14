FROM python:3.11-slim


RUN adduser --disabled-password --gecos "" appuser


WORKDIR /home/appuser/app


ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt


COPY fast_api.py .
COPY model.pkl .


ENV UVICORN_WORKERS=1
ENV UVICORN_TIMEOUT=5


USER appuser

CMD ["python", "-m", "uvicorn", "fast_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "5"]


