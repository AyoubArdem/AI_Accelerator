FROM python:latest

RUN adduser -m appuser
USER appuser

WORKDIR home/appuser/app

COPY requirements.txt  .

RUN pip install --no-cache-dir -r  requirements.txt

COPY fastapi.py .
COPY model.pkl .

ENV UVICORN_WORKERS=1
ENV UVICORN_TIMEOUT=5

CMD ['uvicorn' , 'app:fastapi' , '--host 0.0.0.0' , '--port' , '8000']



