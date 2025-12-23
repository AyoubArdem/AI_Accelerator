FROM python:3.11-slim


RUN adduser -m appuser
USER appuser


WORKDIR /home/appuser/app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY fast_api.py .
COPY model.pkl .


ENV UVICORN_WORKERS=1
ENV UVICORN_TIMEOUT=5


CMD ["uvicorn", "fastapi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "5"]


