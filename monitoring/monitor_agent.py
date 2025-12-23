from fastapi import FastAPI
import os, time, logging, requests

try:
    import psutil
except:
    psutil = None


app=FastAPI()

logger = logging.getLogger("monitor_agent")
logging.basicConfig(level=logging.INFO)

URL_MONITORING = "http://localhost:8000/api/predict"

def measure_latency(url: str):
    try:
        start = time.time()
        requests.post(url, timeout=3.0)
        end = time.time()
        return (end - start) * 1000.0  
    except Exception as e:
        logger.debug(f"Latency measure failed: {e}")
        return None

def collect_metrics():
    try:
        if psutil:
            ram_usage = psutil.virtual_memory()
            cpu_usage = psutil.cpu_percent(interval=0.1)
        else:
            ram_usage = 0.0
            cpu_usage = 0.0
        latency_value = measure_latency(URL_MONITORING)
    except Exception as e:
        logger.exception("psutil error")
        ram_usage = 0.0
        cpu_usage = 0.0
        latency_value = None
    return {
        "cpu_usage": cpu_usage,
        "ram_usage": {
            "total ram(GB)":ram_usage.total,
            "ram_usage_used(GB)":ram_usage.used/1024**3,
            "ram_usage_available":ram_usage.available/1024**3,
            "ram_usage(%)":ram_usage.percent/1024**3,
                      },
        "latency_ms": latency_value,
        "timestamp": int(time.time())
    }

@app.get("/metrics")
def get_metrics():
    return collect_metrics()



















