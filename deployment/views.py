from django.shortcuts import render
from .models import Deployment, ModelVersion, Projet
from .serializers import DeploymentSerializer, ModelVersionSerializer, ProjetSerializer
from rest_framework import viewsets , generics
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics 
from rest_framework.views import APIView
from rest_framework.response import Response
from .Tasks import deploy_model_task
from celery import current_app
from monitoring.models import DeploymentStats, DeploymentAlert, DataDrift
import requests
import time
import numpy as np
import joblib
import pickle
from monitoring.models import Samples

# Create your views here.

def _has_active_celery_worker() -> bool:
    try:
        inspector = current_app.control.inspect(timeout=1.0)
        if inspector is None:
            return False
        ping_result = inspector.ping()
        return bool(ping_result)
    except Exception:
        return False


def _runtime_urls_for_deployment(deployment: Deployment) -> dict:
    base_url = f"http://127.0.0.1:{deployment.port}"
    return {
        "base_url": base_url,
        "ui_page": f"{base_url}/ui",
        "ui_docs": f"{base_url}/docs",
        "ui_redoc": f"{base_url}/redoc",
        "health": f"{base_url}/health",
        "predict": f"{base_url}/predict",
        "predict_decision": f"{base_url}/predict-decision",
    }


class ProjectViewSet(generics.ListCreateAPIView):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [IsAuthenticated]



class ProjectDelete(generics.DestroyAPIView):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [IsAuthenticated]

class ModelVersionViewset(generics.ListCreateAPIView):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]

class ModelVersionDelete(generics.DestroyAPIView):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]

class CreateDeploymentView(viewsets.ModelViewSet):
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        deployment = serializer.save(status=Deployment.StatusChoices.PENDING)
        try:
            if _has_active_celery_worker():
                deploy_model_task.delay(deployment.id)
            else:
                # No worker connected: run synchronously so deployment does not stay queued forever.
                deploy_model_task.apply(args=[deployment.id])
        except Exception:
            deploy_model_task.apply(args=[deployment.id])

class ListDeploymentsView(generics.ListAPIView):
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Deployment.objects.filter(user=self.request.user)


class DeploymentDetailView(generics.RetrieveAPIView):
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

class RedeployView(generics.GenericAPIView):
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, deployment_id):
        try:
            try:
                if _has_active_celery_worker():
                    deploy_model_task.delay(deployment_id)
                else:
                    deploy_model_task.apply(args=[deployment_id])
            except Exception:
                deploy_model_task.apply(args=[deployment_id])
            return Response({"message": "Redeployment started."})
        except Exception:
            return Response({"error": "Invalid deployment id"}, status=400)


   


class StopDeploymentView(generics.GenericAPIView):
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, deployment_id):
        try:
            deployment = Deployment.objects.get(id=deployment_id)

            if not deployment.docker_container_id:
                return Response({"error": "No running container"}, status=400)

            import subprocess

            subprocess.run(
                ["docker", "stop", deployment.docker_container_id],
                check=True
            )

            deployment.status = Deployment.StatusChoices.STOP
            deployment.save()

            return Response({"message": "Deployment stopped"})

        except Exception as e:
            return Response({"error": str(e)}, status=400)



class DeleteDeploymentView(generics.GenericAPIView):
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, deployment_id):
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            import subprocess

            
            if deployment.docker_container_id:
                subprocess.run(["docker", "stop", deployment.docker_container_id], stderr=subprocess.PIPE)

            
            subprocess.run(["docker", "rm", deployment.docker_container_id], stderr=subprocess.PIPE)

    
            image_name = f"deploy_image_{deployment.id}"
            subprocess.run(["docker", "rmi", image_name], stderr=subprocess.PIPE)

            deployment.status = Deployment.StatusChoices.DELETED
            deployment.save()

            return Response({"message": "Deployment deleted"})

        except Exception as e:
            return Response({"error": str(e)}, status=400)


class DeploymentAdvisorAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deployment_id):
        deployment = Deployment.objects.filter(id=deployment_id).first()
        if not deployment:
            return Response({"error": "Deployment not found"}, status=404)

        is_admin = getattr(request.user, "is_superuser", False) or getattr(request.user, "role", None) == "admin"
        if not is_admin and deployment.user_id != request.user.id:
            return Response({"error": "Access denied"}, status=403)

        stats = DeploymentStats.objects.filter(deployment=deployment).first()
        unresolved_alerts = DeploymentAlert.objects.filter(deployment=deployment, resolved=False)
        latest_drift = DataDrift.objects.filter(model_version=deployment.model_version).order_by("-scanned_at").first()

        cpu = float(stats.cpu_usage) if stats else 0.0
        ram = float(stats.ram_usage) if stats else 0.0
        latency = float(stats.latency_ms) if stats else 0.0
        requests = int(stats.request_count) if stats else 0
        errors = int(stats.error_count) if stats else 0
        error_rate = (errors / requests * 100.0) if requests > 0 else 0.0

        score = 100
        reasons = []

        if deployment.status in {Deployment.StatusChoices.FAILED, Deployment.StatusChoices.DELETED}:
            score -= 60
            reasons.append(f"Deployment status is {deployment.status}.")
        elif deployment.status in {Deployment.StatusChoices.PENDING, Deployment.StatusChoices.DEPLOYING}:
            score -= 20
            reasons.append(f"Deployment status is {deployment.status}.")

        if cpu >= 90:
            score -= 15
            reasons.append("CPU usage is very high.")
        elif cpu >= 80:
            score -= 8
            reasons.append("CPU usage is elevated.")

        if ram >= 90:
            score -= 15
            reasons.append("RAM usage is very high.")
        elif ram >= 80:
            score -= 8
            reasons.append("RAM usage is elevated.")

        if latency >= 1000:
            score -= 15
            reasons.append("Latency is very high.")
        elif latency >= 500:
            score -= 8
            reasons.append("Latency is elevated.")

        if error_rate >= 10:
            score -= 15
            reasons.append("Error rate is high.")
        elif error_rate >= 5:
            score -= 8
            reasons.append("Error rate is elevated.")

        if unresolved_alerts.count() > 0:
            score -= min(unresolved_alerts.count() * 4, 16)
            reasons.append(f"{unresolved_alerts.count()} unresolved alerts detected.")

        drift_high = False
        if latest_drift and (
            latest_drift.kl_divergence > 0.25
            or latest_drift.wasserstein_distance > 0.2
            or latest_drift.ks_statistic > 0.3
            or latest_drift.chi_square > 10.0
        ):
            drift_high = True
            score -= 10
            reasons.append("Recent drift metrics exceed recommended thresholds.")

        score = max(0, score)

        if score >= 80:
            risk = "low"
            strategy = "proceed"
        elif score >= 55:
            risk = "medium"
            strategy = "canary"
        elif score >= 35:
            risk = "high"
            strategy = "redeploy"
        else:
            risk = "critical"
            strategy = "rollback"

        recommendations = []
        if strategy == "proceed":
            recommendations.append("Deployment is stable. Continue with standard monitoring.")
        if strategy == "canary":
            recommendations.append("Use canary rollout and monitor latency/error changes closely.")
        if strategy == "redeploy":
            recommendations.append("Redeploy after addressing runtime bottlenecks and unresolved alerts.")
        if strategy == "rollback":
            recommendations.append("Rollback recommended. Investigate logs and restore last healthy version.")
        if drift_high:
            recommendations.append("Retrain or recalibrate model due to elevated drift.")

        return Response(
            {
                "deployment_id": deployment.id,
                "status": deployment.status,
                "advisor_score": score,
                "risk_level": risk,
                "recommended_strategy": strategy,
                "metrics": {
                    "cpu_usage": cpu,
                    "ram_usage": ram,
                    "latency_ms": latency,
                    "request_count": requests,
                    "error_count": errors,
                    "error_rate_pct": round(error_rate, 4),
                },
                "unresolved_alerts": unresolved_alerts.count(),
                "drift_high": drift_high,
                "reasons": reasons,
                "recommendations": recommendations,
            },
            status=200,
        )


def _load_model_for_shadow(path: str):
    try:
        return joblib.load(path), ""
    except Exception:
        try:
            with open(path, "rb") as f:
                return pickle.load(f), ""
        except ModuleNotFoundError as e:
            missing_module = str(e).replace("No module named ", "").strip().strip("'\"")
            if missing_module == "sklearn":
                return None, (
                    "Missing dependency `scikit-learn` in backend environment. "
                    "Install it, then retry traffic-shadow."
                )
            return None, (
                f"Missing dependency `{missing_module}` in backend environment. "
                "Install it, then retry traffic-shadow."
            )
        except Exception as e:
            return None, f"Unsupported or unreadable model format: {e}"


def _predict_batch(model, features: list[list[float]]):
    arr = np.array(features, dtype=float)
    started = time.perf_counter()
    preds = model.predict(arr)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if hasattr(preds, "tolist"):
        preds = preds.tolist()
    return preds, elapsed_ms


class DeploymentTrafficShadowAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deployment_id):
        deployment = Deployment.objects.filter(id=deployment_id).first()
        if not deployment:
            return Response({"error": "Deployment not found"}, status=404)

        is_admin = getattr(request.user, "is_superuser", False) or getattr(request.user, "role", None) == "admin"
        if not is_admin and deployment.user_id != request.user.id:
            return Response({"error": "Access denied"}, status=403)

        candidate_id = request.query_params.get("candidate_model_version_id")
        if not candidate_id:
            return Response({"error": "candidate_model_version_id is required"}, status=400)
        try:
            candidate_id = int(candidate_id)
        except (TypeError, ValueError):
            return Response({"error": "candidate_model_version_id must be an integer"}, status=400)

        sample_limit = request.query_params.get("sample_limit", 200)
        try:
            sample_limit = max(10, min(int(sample_limit), 1000))
        except (TypeError, ValueError):
            return Response({"error": "sample_limit must be an integer"}, status=400)

        candidate_mv = ModelVersion.objects.filter(id=candidate_id).first()
        if not candidate_mv:
            return Response({"error": "Candidate model version not found"}, status=404)

        current_path = deployment.model_version.field_file.path
        candidate_path = candidate_mv.field_file.path

        current_model, current_err = _load_model_for_shadow(current_path)
        if current_model is None:
            return Response({"error": f"Current model load failed: {current_err}"}, status=400)
        candidate_model, candidate_err = _load_model_for_shadow(candidate_path)
        if candidate_model is None:
            return Response({"error": f"Candidate model load failed: {candidate_err}"}, status=400)

        sample_rows = list(
            Samples.objects.filter(model_version=deployment.model_version)
            .order_by("-created_at")[:sample_limit]
        )
        if not sample_rows:
            return Response(
                {
                    "error": "No samples available for shadow test. "
                    "Upload samples with `monitoring samples` first."
                },
                status=400,
            )

        features = []
        for row in sample_rows:
            value = row.data
            if isinstance(value, list):
                try:
                    features.append([float(v) for v in value])
                except (TypeError, ValueError):
                    continue
            else:
                try:
                    features.append([float(value)])
                except (TypeError, ValueError):
                    continue

        if len(features) < 10:
            return Response(
                {"error": "Not enough numeric samples for shadow test (need at least 10)."},
                status=400,
            )

        try:
            current_preds, current_latency_ms = _predict_batch(current_model, features)
            candidate_preds, candidate_latency_ms = _predict_batch(candidate_model, features)
        except Exception as e:
            return Response({"error": f"Prediction failed during shadow test: {e}"}, status=400)

        if len(current_preds) != len(candidate_preds):
            return Response({"error": "Prediction output shape mismatch between models."}, status=400)

        def _to_key(v):
            if isinstance(v, float):
                return round(v, 6)
            return str(v)

        matches = sum(1 for a, b in zip(current_preds, candidate_preds) if _to_key(a) == _to_key(b))
        match_rate = matches / len(current_preds) if current_preds else 0.0

        avg_abs_diff = None
        try:
            a = np.array(current_preds, dtype=float)
            b = np.array(candidate_preds, dtype=float)
            avg_abs_diff = float(np.mean(np.abs(a - b)))
        except Exception:
            avg_abs_diff = None

        latency_ratio = (candidate_latency_ms / current_latency_ms) if current_latency_ms > 0 else 1.0
        if match_rate >= 0.95 and latency_ratio <= 1.10:
            recommendation = "promote_candidate"
            decision_reason = "High prediction agreement and acceptable latency."
        elif match_rate >= 0.85 and latency_ratio <= 1.25:
            recommendation = "canary_candidate"
            decision_reason = "Moderate agreement; canary rollout is safer."
        else:
            recommendation = "keep_current"
            decision_reason = "Candidate diverges too much or latency impact is high."

        return Response(
            {
                "deployment_id": deployment.id,
                "current_model_version_id": deployment.model_version.id,
                "candidate_model_version_id": candidate_mv.id,
                "sample_count": len(features),
                "shadow_metrics": {
                    "prediction_match_rate": round(match_rate, 6),
                    "prediction_matches": matches,
                    "current_latency_ms": round(current_latency_ms, 4),
                    "candidate_latency_ms": round(candidate_latency_ms, 4),
                    "latency_ratio_candidate_vs_current": round(latency_ratio, 6),
                    "avg_abs_prediction_diff": round(avg_abs_diff, 6) if avg_abs_diff is not None else None,
                },
                "recommendation": recommendation,
                "reason": decision_reason,
            },
            status=200,
        )


class DeploymentServiceCatalogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deployment_id):
        deployment = Deployment.objects.filter(id=deployment_id).first()
        if not deployment:
            return Response({"error": "Deployment not found"}, status=404)

        is_admin = getattr(request.user, "is_superuser", False) or getattr(request.user, "role", None) == "admin"
        if not is_admin and deployment.user_id != request.user.id:
            return Response({"error": "Access denied"}, status=403)

        probe = str(request.query_params.get("probe", "false")).lower() in {"1", "true", "yes", "y"}
        timeout_s = request.query_params.get("timeout", 2)
        try:
            timeout_s = max(1, min(int(timeout_s), 10))
        except (TypeError, ValueError):
            return Response({"error": "timeout must be an integer"}, status=400)

        urls = _runtime_urls_for_deployment(deployment)
        health_ok = None
        health_payload = None
        health_error = None

        if probe:
            try:
                resp = requests.get(urls["health"], timeout=timeout_s)
                health_ok = resp.status_code == 200
                try:
                    health_payload = resp.json()
                except Exception:
                    health_payload = {"raw": resp.text[:500]}
            except Exception as e:
                health_ok = False
                health_error = str(e)

        return Response(
            {
                "deployment_id": deployment.id,
                "status": deployment.status,
                "docker_container_id": deployment.docker_container_id,
                "services": urls,
                "probe": {
                    "enabled": probe,
                    "health_ok": health_ok,
                    "health_response": health_payload,
                    "health_error": health_error,
                },
            },
            status=200,
        )



