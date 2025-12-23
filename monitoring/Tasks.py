from celery import shared_task
import deployment
from monitoring.models import DeploymentMonitoringRecord
import requests
import docker

@shared_task(bind=True)
def CollectAndStoreMetrics(deployment_id):
    from deployment.models import Deployment

    client = docker.from_env()
    deploy = Deployment.objects.get(id =deployment_id)
   
    if deploy.DoesNotExist():
            raise ValueError("this deployment is not exist")
    
    URL = "http://localhost:{deploy.port}/metrics"
    metrics = requests.get(URL) 

    DeploymentMonitoringRecord.objects.create(
        deployment = deploy,
        cpu_usage = metrics['cpu_usage'],
        ram_usage = metrics['ram_usage'],
        latency_ms = metrics['latency_ms'],
        created_at = metrics['timestamp']
    )
    
    try:
        container = client.containers.get(deployment.docker_container_id)
        stats = container.stats(stream=False)

        cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        ram_usage = stats["memory_stats"]["usage"]

        payload = {
            "deployment_id": deploy.id,
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage,
            "latency_ms": metrics['latency_ms'],
            "request_count": 0,
            "error_count": 0,
        }

        

        requests.post("http://deployments/{deploy.id}/alerts/", json=payload)

    except Exception as e:
        print("Error:", e)

    
