from celery import shared_task
from monitoring.models import Samples
from monitoring.models import DeploymentMonitoringRecord , DataDrift 
import requests
import docker
from deployment.models import ModelVersion
import numpy as np
from drift_utils import calculate_kl_divergence, calculate_wasserstein_distance, calculate_ks_statistic, calculate_chi_square
from governance.utils import LogAction


@shared_task(bind=True)
def CollectAndStoreMetrics(deployment_id):
    """
    Docstring for CollectAndStoreMetrics
    
    :param deployment_id: Description
    """
    from deployment.models import Deployment

    client = docker.from_env()
    try:
        deploy = Deployment.objects.get(id=deployment_id)
    except Deployment.DoesNotExist:
        raise ValueError("This deployment does not exist")
    
    URL = f"http://localhost:{deploy.port}/metrics"
    response = requests.get(URL)
    
    if response.status_code == 200:
        metrics = response.json()
        count_request = 1
        count_error = 0
    else:
        raise ValueError("Failed to fetch metrics")
    
    DeploymentMonitoringRecord.objects.create(
        deployment=deploy,
        cpu_usage=metrics['cpu_usage'],
        ram_usage=metrics['ram_usage'],
        latency_ms=metrics['latency_ms'],
        request_count=count_request,
        error_count=count_error,
        created_at=metrics['timestamp']
    )
    
    try:
        container = client.containers.get(deploy.docker_container_id)
        stats = container.stats(stream=False)

        cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        ram_usage = stats["memory_stats"]["usage"]

        payload = {
            "deployment_id": deploy.id,
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage,
            "latency_ms": metrics['latency_ms'],
            "request_count": count_request,
            "error_count": count_error,
        }

        

        requests.post(f"http://localhost:{deploy.port}/alerts/", json=payload)

    except Exception as e:
        print("Error:", e)

    
@shared_task(bind=True)
def detect_drift(model_version_id):
    """
    Docstring for detect_drift
    
    :param model_version_id: Description
    """
    Psi_threshold = 0.25
    wasserstein_distance_threshold = 0.2
    ks_statistic_threshold = 0.3
    chi_square_threshold = 10.0

    from deployment.models import Deployment
    deployment = Deployment.objects.filter(model_version__id=model_version_id).first()

    try:
        model_version = ModelVersion.objects.get(id=model_version_id)
    except ModelVersion.DoesNotExist:
        raise ValueError("Model version does not exist")
    # Fetch baseline and current data samples
    baseline_data = model_version.sample_data  # Assuming sample_data is the baseline
    # For current data, perhaps get from recent samples or pass as parameter
    # For now, assume current_data is similar or from Samples
    current_samples = Samples.objects.filter(model_version=model_version).order_by('-created_at')[:100]  # Get recent samples
    current_data = []
    for sample in current_samples:
        # Assuming data is JSON or list
        current_data.extend(sample.data)  # Adjust based on data type

    if not baseline_data or not current_data:
        raise ValueError("Insufficient data for drift detection")
    # Convert to numpy arrays for processing
    baseline_array = np.array(baseline_data)
    current_array = np.array(current_data)

    # Calculate drift metrics
    kl_divergence = calculate_kl_divergence(baseline_array, current_array)
    wasserstein_distance = calculate_wasserstein_distance(baseline_array, current_array)
    ks_statistic = calculate_ks_statistic(baseline_array, current_array)
    chi_square = calculate_chi_square(baseline_array, current_array)

    # Store drift results
    drift_results = {
        "kl_divergence": kl_divergence,
        "wasserstein_distance": wasserstein_distance,
        "ks_statistic": ks_statistic,
        "chi_square": chi_square,
    }
    if deployment.user.role == "admin": 
        role_permissions = { "role": "admin", "permissions": [ "deployment:*", "monitoring:*", "governance:*", "audit:read" ] }

    elif deployment.user.role == "engineer":
        role_permissions = { "role": "engineer", "permissions": [ "deployment:read", "deployment:write", "monitoring:read" ] }

    else: role_permissions = { "role": "auditor", "permissions": [ "audit:read" ] }

    if kl_divergence > Psi_threshold or wasserstein_distance > wasserstein_distance_threshold or ks_statistic > ks_statistic_threshold or chi_square > chi_square_threshold:
      meta_data = {
        "role_permissions": [
            role_permissions
            ], 
        "deployment": [
            {
                "id": deployment.id,
                "name": deployment.name,
                "port": deployment.port,
                "status": deployment.status,
            }
            ],
        "drift_monitoring": {
            "enabled": True,
            "check_strategy": {
                "type": "request_based",
                "every_n_requests": 1000,
                "interval_minutes": 60   
            }
        },
    
        "metrics": [
            {
                "name": "psi",
                "enabled": True,
                "warning": 0.15,
                "critical": 0.25
            },
            {
                "name": "ks_test",
                "enabled": True,
                "p_value_threshold": 0.05
            },
            {
                "name": "wasserstein",
                "enabled": True,
                "warning": 0.2
            },
            {
                "name": "kl_divergence",
                "enabled": True,
                "critical": 0.25
            },
            {
                "name": "chi_square",
                "enabled": True,
                "critical": 10.0
            }
        ]}
      
      LogAction(
            user=deployment.user,
            action="DRIFT DETECTED",
            description=f"Data drift detected for model version {model_version.id} in deployment {deployment.name}.",
            metadata=meta_data,
            service="monitoring",
            deployment=deployment
        )

    if (kl_divergence > Psi_threshold or
        wasserstein_distance > wasserstein_distance_threshold or
        ks_statistic > ks_statistic_threshold or
        chi_square > chi_square_threshold):
        
        DataDrift.objects.create(
            model_version=model_version,
            kl_divergence=kl_divergence,
            wasserstein_distance=wasserstein_distance,
            ks_statistic=ks_statistic,
            chi_square=chi_square,
            results=drift_results,
            sample_count=len(current_data)
        )