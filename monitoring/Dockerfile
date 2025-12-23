
FROM python:3.11-slim

WORKDIR /monitor_app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor_agent.py .

CMD ["uvicorn", "monitor_app:app", "--host", "0.0.0.0", "--port", "8000"]