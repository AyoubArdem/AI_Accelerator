from celery import shared_task
from monitoring.models import Samples
from monitoring.models import DeploymentMonitoringRecord, DeploymentStats, DeploymentAlert, DataDrift
import requests
import docker
import time
from deployment.models import ModelVersion, Deployment
import numpy as np
# Support both package and direct module execution contexts.
try:
    from monitoring.drift_utils import (
        calculate_kl_divergence,
        calculate_wasserstein_distance,
        calculate_ks_statistic,
        calculate_chi_square,
    )
except ModuleNotFoundError:
    from drift_utils import (
        calculate_kl_divergence,
        calculate_wasserstein_distance,
        calculate_ks_statistic,
        calculate_chi_square,
    )
from governance.utils import LogAction

@shared_task(bind=True)
def start_monitor_agent(self, deployment_id, interval_seconds=30):
    """
    Trigger a metrics collection run for a deployment.
    This is a lightweight starter task invoked after deployment.
    """
    try:
        return CollectAndStoreMetrics.delay(
            deployment_id,
            schedule_next=True,
            interval_seconds=interval_seconds,
        )
    except Exception:
        # In fallback mode (no worker), run one synchronous collection only.
        return CollectAndStoreMetrics.apply(
            args=[deployment_id],
            kwargs={"schedule_next": False, "interval_seconds": interval_seconds},
        )

@shared_task
def CollectAndStoreMetrics(deployment_id, schedule_next=False, interval_seconds=30):
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

    count_request = 1
    count_error = 0
    latency_ms = 0.0

    def _extract_features():
        sample = deploy.model_version.sample_data
        if isinstance(sample, dict):
            value = sample.get("features")
            return value if isinstance(value, list) else None
        if isinstance(sample, list) and sample:
            first = sample[0]
            if isinstance(first, list):
                return first
            if isinstance(first, (int, float)):
                return sample
        return None

    features = _extract_features()
    predict_url = f"http://127.0.0.1:{deploy.port}/predict"
    health_url = f"http://127.0.0.1:{deploy.port}/health"
    try:
        start = time.monotonic()
        if features:
            resp = requests.post(predict_url, json={"features": features}, timeout=5)
        else:
            resp = requests.get(health_url, timeout=3)
        end = time.monotonic()
        latency_ms = (end - start) * 1000.0
        if resp.status_code >= 400:
            count_error = 1
    except Exception:
        count_error = 1

    # Prefer runtime counters when available. /metrics exposes cumulative totals.
    # Keep backward compatibility by falling back to probe-based counters above.
    runtime_request_total = None
    runtime_error_total = None
    metrics_url = f"http://127.0.0.1:{deploy.port}/metrics"
    try:
        metrics_resp = requests.get(metrics_url, timeout=3)
        if metrics_resp.status_code < 400:
            metrics_payload = metrics_resp.json() if metrics_resp.text else {}
            runtime_request_total = int(metrics_payload.get("request_count", 0))
            runtime_error_total = int(metrics_payload.get("error_count", 0))
    except Exception:
        runtime_request_total = None
        runtime_error_total = None

    cpu_usage = 0.0
    ram_usage = 0.0
    try:
        container = client.containers.get(deploy.docker_container_id)
        stats = container.stats(stream=False)

        # Convert to practical percentages/MB for display.
        cpu_total = float(stats["cpu_stats"]["cpu_usage"].get("total_usage", 0.0))
        pre_cpu_total = float(stats["precpu_stats"]["cpu_usage"].get("total_usage", 0.0))
        system_total = float(stats["cpu_stats"].get("system_cpu_usage", 0.0))
        pre_system_total = float(stats["precpu_stats"].get("system_cpu_usage", 0.0))
        cpu_delta = cpu_total - pre_cpu_total
        system_delta = system_total - pre_system_total
        cpu_count = max(len(stats["cpu_stats"].get("cpu_usage", {}).get("percpu_usage", []) or [1]), 1)
        if system_delta > 0 and cpu_delta > 0:
            cpu_usage = (cpu_delta / system_delta) * cpu_count * 100.0

        ram_bytes = float(stats.get("memory_stats", {}).get("usage", 0.0))
        ram_usage = ram_bytes / (1024.0 * 1024.0)
    except Exception:
        # Keep defaults; monitoring should still persist heartbeat records.
        pass

    payload = {
        "deployment_id": deploy.id,
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "latency_ms": latency_ms,
        "request_count": count_request,
        "error_count": count_error,
    }

    stats, _ = DeploymentStats.objects.get_or_create(
        deployment=deploy,
        defaults={
            "cpu_usage": payload["cpu_usage"],
            "ram_usage": payload["ram_usage"],
            "latency_ms": payload["latency_ms"],
            "request_count": payload["request_count"],
            "error_count": payload["error_count"],
        },
    )
    previous_total_requests = int(stats.request_count or 0)
    previous_total_errors = int(stats.error_count or 0)

    # Store per-record deltas, while stats keep cumulative totals.
    if runtime_request_total is not None and runtime_error_total is not None:
        count_request = max(runtime_request_total - previous_total_requests, 0)
        count_error = max(runtime_error_total - previous_total_errors, 0)
        total_request_count = max(runtime_request_total, previous_total_requests)
        total_error_count = max(runtime_error_total, previous_total_errors)
    else:
        total_request_count = previous_total_requests + int(payload["request_count"])
        total_error_count = previous_total_errors + int(payload["error_count"])

    # Record deltas for time-series analysis.
    payload["request_count"] = int(count_request)
    payload["error_count"] = int(count_error)

    # Persist the monitoring sample with delta values.
    DeploymentMonitoringRecord.objects.create(
        deployment=deploy,
        cpu_usage=payload["cpu_usage"],
        ram_usage=payload["ram_usage"],
        latency_ms=payload["latency_ms"],
        request_count=payload["request_count"],
        error_count=payload["error_count"],
    )

    # Persist cumulative counters in stats.
    stats.cpu_usage = payload["cpu_usage"]
    stats.ram_usage = payload["ram_usage"]
    stats.latency_ms = payload["latency_ms"]
    stats.request_count = int(total_request_count)
    stats.error_count = int(total_error_count)
    stats.save()

    # Generate alerts directly from collected stats (same thresholds as API view).
    def _create_alert_once(alert_type: str, message: str):
        existing = DeploymentAlert.objects.filter(
            deployment=deploy,
            alert_type=alert_type,
            resolved=False,
        ).exists()
        if not existing:
            DeploymentAlert.objects.create(
                deployment=deploy,
                alert_type=alert_type,
                message=message,
            )

    if stats.cpu_usage > 80:
        _create_alert_once("high_cpu", f"CPU usage reached {stats.cpu_usage}%")
    if stats.ram_usage > 2000:
        _create_alert_once("high_ram", f"RAM usage reached {stats.ram_usage} MB")
    if stats.latency_ms > 1000:
        _create_alert_once("latency_spike", f"Latency reached {stats.latency_ms} ms")
    if stats.error_count > 5:
        _create_alert_once("errors_spike", f"Errors detected: {stats.error_count}")

    if schedule_next and deploy.status == Deployment.StatusChoices.ACTIVE:
        try:
            CollectAndStoreMetrics.apply_async(
                args=[deployment_id],
                kwargs={"schedule_next": True, "interval_seconds": interval_seconds},
                countdown=interval_seconds,
            )
        except Exception:
            # If queueing the next tick fails, keep current metrics and exit gracefully.
            pass

    
@shared_task
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
            action="DRIFT_DETECTED",
            description=f"Data drift detected for model version {model_version.id} in deployment {deployment.id}.",
            metadata=meta_data,
            service="monitoring",
            deployment=deployment,
            severity="high",
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
