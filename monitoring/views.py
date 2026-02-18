from django.shortcuts import render
from rest_framework import generics,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from deployment.models import Deployment, ModelVersion
from rest_framework.response import Response
import numpy as np
from django.utils import timezone
from datetime import timedelta
from .models import (
    DataDrift,
    DeploymentMonitoringRecord,
    DeploymentStats,
    DeploymentAlert,
    Samples
)
from .serializers import (
    DeploymentMonitoringRecordSerializer,
    DeploymentStatsSerializer,
    DeploymentAlertSerializer,
    DataDriftSerializer,
    SamplesSerializer
      )
from monitoring.models import Samples
from monitoring.drift_utils import (
    calculate_kl_divergence,
    calculate_wasserstein_distance,
    calculate_ks_statistic,
    calculate_chi_square,
)

class DeploymentStatsAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeploymentStatsSerializer
    lookup_field = "deployment_id"
    lookup_url_kwarg = "deployment_id"

    def get_queryset(self):
        return DeploymentStats.objects.all()

    def get(self, request, *args, **kwargs):
        deployment_id = kwargs.get("deployment_id")
        if not Deployment.objects.filter(id=deployment_id).exists():
            return Response({"error": "Deployment not found"}, status=404)

        stats = DeploymentStats.objects.filter(deployment_id=deployment_id).first()
        if not stats:
            return Response(
                {
                    "deployment": deployment_id,
                    "cpu_usage": 0,
                    "ram_usage": 0,
                    "latency_ms": 0,
                    "request_count": 0,
                    "error_count": 0,
                    "updated_at": None,
                },
                status=200,
            )

        serializer = self.get_serializer(stats)
        return Response(serializer.data, status=200)
    

def _is_admin_user(user):
    return getattr(user, "is_superuser", False) or getattr(user, "role", None) == "admin"


class DeploymentHealthReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deployment_id):
        deployment = Deployment.objects.filter(id=deployment_id).first()
        if not deployment:
            return Response({"error": "Deployment not found"}, status=404)

        if not _is_admin_user(request.user) and deployment.user_id != request.user.id:
            return Response({"error": "Access denied"}, status=403)

        window = request.query_params.get("window", 50)
        try:
            window = max(10, min(int(window), 500))
        except (TypeError, ValueError):
            return Response({"error": "window must be an integer"}, status=400)

        records = list(
            DeploymentMonitoringRecord.objects.filter(deployment=deployment)
            .order_by("-created_at")[:window]
        )
        stats = DeploymentStats.objects.filter(deployment=deployment).first()
        unresolved_alerts = DeploymentAlert.objects.filter(deployment=deployment, resolved=False)
        recent_alerts = DeploymentAlert.objects.filter(
            deployment=deployment, created_at__gte=timezone.now() - timedelta(hours=24)
        )
        latest_drift = DataDrift.objects.filter(model_version=deployment.model_version).order_by("-scanned_at").first()

        if records:
            cpu_vals = [float(r.cpu_usage) for r in records]
            ram_vals = [float(r.ram_usage) for r in records]
            lat_vals = [float(r.latency_ms) for r in records]
            req_vals = [int(r.request_count) for r in records]
            err_vals = [int(r.error_count) for r in records]
            avg_cpu = sum(cpu_vals) / len(cpu_vals)
            avg_ram = sum(ram_vals) / len(ram_vals)
            avg_latency = sum(lat_vals) / len(lat_vals)
            total_requests = sum(req_vals)
            total_errors = sum(err_vals)
        elif stats:
            avg_cpu = float(stats.cpu_usage)
            avg_ram = float(stats.ram_usage)
            avg_latency = float(stats.latency_ms)
            total_requests = int(stats.request_count)
            total_errors = int(stats.error_count)
        else:
            avg_cpu = 0.0
            avg_ram = 0.0
            avg_latency = 0.0
            total_requests = 0
            total_errors = 0

        error_rate = (total_errors / total_requests * 100.0) if total_requests > 0 else 0.0

        penalty = 0
        if avg_cpu >= 90:
            penalty += 25
        elif avg_cpu >= 80:
            penalty += 15
        if avg_ram >= 90:
            penalty += 25
        elif avg_ram >= 80:
            penalty += 15
        if avg_latency >= 1000:
            penalty += 25
        elif avg_latency >= 500:
            penalty += 12
        if error_rate >= 10:
            penalty += 20
        elif error_rate >= 5:
            penalty += 10
        penalty += min(unresolved_alerts.count() * 5, 20)
        if latest_drift and (
            latest_drift.kl_divergence > 0.25
            or latest_drift.wasserstein_distance > 0.2
            or latest_drift.ks_statistic > 0.3
            or latest_drift.chi_square > 10
        ):
            penalty += 10

        health_score = max(0, 100 - penalty)
        if health_score >= 80:
            health_status = "healthy"
        elif health_score >= 50:
            health_status = "degraded"
        else:
            health_status = "critical"

        trends = {}
        if len(records) >= 6:
            half = len(records) // 2
            recent = records[:half]
            older = records[half:]
            def _mean(values):
                return sum(values) / len(values) if values else 0.0
            trends = {
                "cpu_trend": _mean([r.cpu_usage for r in recent]) - _mean([r.cpu_usage for r in older]),
                "ram_trend": _mean([r.ram_usage for r in recent]) - _mean([r.ram_usage for r in older]),
                "latency_trend": _mean([r.latency_ms for r in recent]) - _mean([r.latency_ms for r in older]),
            }

        recommendations = []
        if unresolved_alerts.count() > 0:
            recommendations.append("Resolve unresolved deployment alerts.")
        if avg_latency >= 500:
            recommendations.append("Investigate latency bottlenecks and scale serving resources.")
        if error_rate >= 5:
            recommendations.append("Inspect model/service logs and reduce request error rate.")
        if latest_drift and (
            latest_drift.kl_divergence > 0.25
            or latest_drift.wasserstein_distance > 0.2
            or latest_drift.ks_statistic > 0.3
            or latest_drift.chi_square > 10
        ):
            recommendations.append("Drift indicators are high; retrain or recalibrate the model.")
        if not recommendations:
            recommendations.append("System looks healthy. Continue regular monitoring.")

        payload = {
            "deployment_id": deployment.id,
            "status": deployment.status,
            "health_score": health_score,
            "health_status": health_status,
            "window_records": len(records),
            "metrics": {
                "avg_cpu_usage": round(avg_cpu, 4),
                "avg_ram_usage": round(avg_ram, 4),
                "avg_latency_ms": round(avg_latency, 4),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate_pct": round(error_rate, 4),
            },
            "alerts": {
                "unresolved": unresolved_alerts.count(),
                "last_24h": recent_alerts.count(),
            },
            "drift": (
                {
                    "scanned_at": latest_drift.scanned_at,
                    "kl_divergence": latest_drift.kl_divergence,
                    "wasserstein_distance": latest_drift.wasserstein_distance,
                    "ks_statistic": latest_drift.ks_statistic,
                    "chi_square": latest_drift.chi_square,
                }
                if latest_drift
                else None
            ),
            "trends": {k: round(v, 4) for k, v in trends.items()},
            "recommendations": recommendations,
        }
        return Response(payload, status=200)


class DeploymentCostIntelligenceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deployment_id):
        deployment = Deployment.objects.filter(id=deployment_id).first()
        if not deployment:
            return Response({"error": "Deployment not found"}, status=404)

        if not _is_admin_user(request.user) and deployment.user_id != request.user.id:
            return Response({"error": "Access denied"}, status=403)

        window = request.query_params.get("window", 200)
        try:
            window = max(10, min(int(window), 1000))
        except (TypeError, ValueError):
            return Response({"error": "window must be an integer"}, status=400)

        try:
            cpu_hour_rate = float(request.query_params.get("cpu_hour_rate", 0.05))
            gb_ram_hour_rate = float(request.query_params.get("gb_ram_hour_rate", 0.01))
            request_million_rate = float(request.query_params.get("request_million_rate", 1.0))
            ram_reference_gb = float(request.query_params.get("ram_reference_gb", 4.0))
            budget_raw = request.query_params.get("budget_monthly")
            budget_monthly = float(budget_raw) if budget_raw not in (None, "", "null") else None
            target_cpu_utilization = float(request.query_params.get("target_cpu_utilization", 65.0))
            target_ram_utilization = float(request.query_params.get("target_ram_utilization", 70.0))
            include_scenarios = str(request.query_params.get("include_scenarios", "true")).strip().lower() in {"1", "true", "yes", "on"}
        except (TypeError, ValueError):
            return Response({"error": "pricing parameters must be numeric"}, status=400)

        records = list(
            DeploymentMonitoringRecord.objects.filter(deployment=deployment)
            .order_by("-created_at")[:window]
        )
        stats = DeploymentStats.objects.filter(deployment=deployment).first()
        unresolved_alerts = DeploymentAlert.objects.filter(deployment=deployment, resolved=False).count()
        latest_drift = DataDrift.objects.filter(model_version=deployment.model_version).order_by("-scanned_at").first()

        if records:
            avg_cpu = sum(float(r.cpu_usage) for r in records) / len(records)
            avg_ram = sum(float(r.ram_usage) for r in records) / len(records)
            total_requests = sum(int(r.request_count) for r in records)
            newest = records[0].created_at
            oldest = records[-1].created_at
            observed_hours = max((newest - oldest).total_seconds() / 3600.0, 1.0)
        elif stats:
            avg_cpu = float(stats.cpu_usage)
            avg_ram = float(stats.ram_usage)
            total_requests = int(stats.request_count)
            observed_hours = 24.0
        else:
            avg_cpu = 0.0
            avg_ram = 0.0
            total_requests = 0
            observed_hours = 24.0

        if avg_ram > 128:
            avg_ram_gb = avg_ram / 1024.0
        else:
            avg_ram_gb = (avg_ram / 100.0) * max(ram_reference_gb, 0.1)

        monthly_hours = 24.0 * 30.0
        cpu_monthly_cost = (avg_cpu / 100.0) * monthly_hours * max(cpu_hour_rate, 0.0)
        ram_monthly_cost = max(avg_ram_gb, 0.0) * monthly_hours * max(gb_ram_hour_rate, 0.0)
        requests_per_hour = total_requests / observed_hours if observed_hours > 0 else 0.0
        monthly_requests = requests_per_hour * monthly_hours
        request_monthly_cost = (monthly_requests / 1_000_000.0) * max(request_million_rate, 0.0)
        estimated_monthly_total = cpu_monthly_cost + ram_monthly_cost + request_monthly_cost
        annual_estimated_total = estimated_monthly_total * 12.0

        ram_util_pct = (avg_ram_gb / max(ram_reference_gb, 0.1)) * 100.0
        cpu_alignment = max(0.0, 100.0 - abs(avg_cpu - target_cpu_utilization) * 1.5)
        ram_alignment = max(0.0, 100.0 - abs(ram_util_pct - target_ram_utilization) * 1.2)
        drift_high = bool(
            latest_drift and (
                latest_drift.kl_divergence > 0.25
                or latest_drift.wasserstein_distance > 0.2
                or latest_drift.ks_statistic > 0.3
                or latest_drift.chi_square > 10
            )
        )
        penalty = min(unresolved_alerts * 5, 25) + (10 if drift_high else 0)
        efficiency_score = max(0.0, min(100.0, (cpu_alignment * 0.55) + (ram_alignment * 0.45) - penalty))
        if efficiency_score >= 80:
            efficiency_class = "optimized"
        elif efficiency_score >= 55:
            efficiency_class = "acceptable"
        else:
            efficiency_class = "needs_attention"

        recommendations = []
        estimated_savings = 0.0
        if avg_cpu < 30:
            rec_saving = cpu_monthly_cost * 0.25
            estimated_savings += rec_saving
            recommendations.append(
                f"CPU appears over-provisioned (avg {avg_cpu:.2f}%). Right-size compute to save about {rec_saving:.2f}/month."
            )
        if avg_ram_gb < 1.0:
            rec_saving = ram_monthly_cost * 0.30
            estimated_savings += rec_saving
            recommendations.append(
                f"RAM utilization is low (avg {avg_ram_gb:.2f} GB). Reduce memory allocation to save about {rec_saving:.2f}/month."
            )
        if unresolved_alerts > 3:
            recommendations.append(
                "High unresolved alerts can raise incident/ops costs. Triage and resolve alerts promptly."
            )
        if drift_high:
            recommendations.append(
                "Drift is elevated. Retraining can reduce hidden quality and support costs."
            )

        budget = None
        if budget_monthly is not None and budget_monthly >= 0:
            variance = estimated_monthly_total - budget_monthly
            variance_pct = (variance / budget_monthly * 100.0) if budget_monthly > 0 else 0.0
            budget = {
                "monthly_budget": round(budget_monthly, 4),
                "variance": round(variance, 4),
                "variance_pct": round(variance_pct, 4),
                "within_budget": bool(estimated_monthly_total <= budget_monthly),
            }
            if variance > 0:
                recommendations.append(
                    f"Estimated monthly spend exceeds budget by {variance:.2f}. "
                    "Prioritize right-sizing and alert reduction."
                )
            else:
                recommendations.append(
                    f"Estimated monthly spend is under budget by {abs(variance):.2f}. "
                    "Keep utilization monitored to preserve efficiency."
                )

        risks = []
        if avg_cpu < 20:
            risks.append("cpu_underutilized")
        elif avg_cpu > 85:
            risks.append("cpu_saturation_risk")
        if ram_util_pct < 25:
            risks.append("ram_underutilized")
        elif ram_util_pct > 90:
            risks.append("ram_saturation_risk")
        if unresolved_alerts > 5:
            risks.append("operational_alert_pressure")
        if drift_high:
            risks.append("quality_drift_risk")

        scenarios = []
        if include_scenarios:
            def _scenario_total(cpu_factor, ram_factor, req_factor):
                cpu_cost = ((avg_cpu * cpu_factor) / 100.0) * monthly_hours * max(cpu_hour_rate, 0.0)
                ram_cost = max(avg_ram_gb * ram_factor, 0.0) * monthly_hours * max(gb_ram_hour_rate, 0.0)
                req_cost = ((monthly_requests * req_factor) / 1_000_000.0) * max(request_million_rate, 0.0)
                return cpu_cost + ram_cost + req_cost

            baseline = estimated_monthly_total
            right_size = _scenario_total(0.75, 0.8, 1.0)
            growth_scale = _scenario_total(1.25, 1.35, 1.4)
            aggressive_opt = _scenario_total(0.6, 0.65, 1.0)
            scenarios = [
                {
                    "name": "right_size",
                    "estimated_monthly_cost": round(right_size, 4),
                    "delta_vs_current": round(right_size - baseline, 4),
                },
                {
                    "name": "growth_scale",
                    "estimated_monthly_cost": round(growth_scale, 4),
                    "delta_vs_current": round(growth_scale - baseline, 4),
                },
                {
                    "name": "aggressive_optimization",
                    "estimated_monthly_cost": round(aggressive_opt, 4),
                    "delta_vs_current": round(aggressive_opt - baseline, 4),
                },
            ]

        if not recommendations:
            recommendations.append("Cost profile appears balanced. Continue monitoring utilization and alert trends.")

        total_cost_nonzero = estimated_monthly_total if estimated_monthly_total > 0 else 1.0
        payload = {
            "deployment_id": deployment.id,
            "status": deployment.status,
            "window_records": len(records),
            "observed_hours": round(observed_hours, 4),
            "utilization": {
                "avg_cpu_pct": round(avg_cpu, 4),
                "avg_ram_gb": round(avg_ram_gb, 4),
                "requests_per_hour": round(requests_per_hour, 4),
            },
            "pricing": {
                "cpu_hour_rate": cpu_hour_rate,
                "gb_ram_hour_rate": gb_ram_hour_rate,
                "request_million_rate": request_million_rate,
                "ram_reference_gb": ram_reference_gb,
            },
            "cost_breakdown_monthly": {
                "cpu_cost": round(cpu_monthly_cost, 4),
                "ram_cost": round(ram_monthly_cost, 4),
                "request_cost": round(request_monthly_cost, 4),
                "total_estimated_cost": round(estimated_monthly_total, 4),
                "cpu_share_pct": round(cpu_monthly_cost / total_cost_nonzero * 100.0, 4),
                "ram_share_pct": round(ram_monthly_cost / total_cost_nonzero * 100.0, 4),
                "request_share_pct": round(request_monthly_cost / total_cost_nonzero * 100.0, 4),
            },
            "annual_estimated_cost": round(annual_estimated_total, 4),
            "efficiency": {
                "score": round(efficiency_score, 4),
                "classification": efficiency_class,
                "target_cpu_utilization": round(target_cpu_utilization, 4),
                "target_ram_utilization": round(target_ram_utilization, 4),
                "current_ram_utilization_pct": round(ram_util_pct, 4),
            },
            "budget": budget,
            "risks": risks,
            "optimization": {
                "estimated_savings_potential": round(estimated_savings, 4),
                "recommendations": recommendations,
            },
            "scenarios": scenarios,
        }
        return Response(payload, status=200)


class DeploymentAlertsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeploymentAlertSerializer

    def get_queryset(self):
        deployment_id = self.kwargs["deployment_id"]
        return DeploymentAlert.objects.filter(deployment=deployment_id).order_by("-created_at")
    
class DeploymentRecordsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeploymentMonitoringRecordSerializer

    def get_queryset(self):
        deployment_id = self.kwargs["deployment_id"]
        return DeploymentMonitoringRecord.objects.filter(deployment=deployment_id).order_by("-created_at")



class ReceiveMetricsAPIView(APIView):

    def get(self, request, deployment_id):
        alerts = DeploymentAlert.objects.filter(deployment=deployment_id).order_by("-created_at")
        serializer = DeploymentAlertSerializer(alerts, many=True)
        return Response(serializer.data, status=200)

    def post(self, request, deployment_id=None):
        data = request.data
        deployment_id = deployment_id or data.get("deployment_id")

        
        try:
            deployment = Deployment.objects.get(id=deployment_id)
        except Deployment.DoesNotExist:
            return Response(
                {"error": "Invalid deployment_id"},
                status=status.HTTP_404_NOT_FOUND
            )

       
        record_serializer = DeploymentMonitoringRecordSerializer(data=data)
        record_serializer.is_valid(raise_exception=True)
        record_serializer.save()

       
        stats, created = DeploymentStats.objects.get_or_create(deployment=deployment)
        stats.cpu_usage = data["cpu_usage"]
        stats.ram_usage = data["ram_usage"]
        stats.latency_ms = data["latency_ms"]
        stats.request_count = data["request_count"]
        stats.error_count = data["error_count"]
        stats.save()

        
        self.check_alerts(deployment, stats)

        return Response({"status": "OK",
                         "metrics received": record_serializer.data}
                         , status=200)

    def check_alerts(self, deployment, stats):
       

        if stats.cpu_usage > 80:
            DeploymentAlert.objects.create(
                deployment=deployment,
                alert_type="high_cpu",
                message=f"CPU usage reached {stats.cpu_usage}%"
            )

        if stats.ram_usage > 2000:
            DeploymentAlert.objects.create(
                deployment=deployment,
                alert_type="high_ram",
                message=f"RAM usage reached {stats.ram_usage} MB"
            )

        if stats.latency_ms > 1000:
            DeploymentAlert.objects.create(
                deployment=deployment,
                alert_type="latency_spike",
                message=f"Latency reached {stats.latency_ms} ms"
            )

        if stats.error_count > 5:
            DeploymentAlert.objects.create(
                deployment=deployment,
                alert_type="errors_spike",
                message=f"Errors detected: {stats.error_count}"
            )



class ResolveAlertAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        try:
            alert = DeploymentAlert.objects.get(id=alert_id)
        except DeploymentAlert.DoesNotExist:
            return Response({"error": "Alert not found"}, status=404)

        alert.resolved = True
        alert.save()

        return Response({"status": "resolved"}, status=200)

class GetSamplesAPIView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SamplesSerializer

    def post(self, request):
        model_version_id = request.data.get("model_version_id")
        if not model_version_id:
            return Response({"error": "model_version_id is required"}, status=400)

        try:
            model_version = ModelVersion.objects.get(id=model_version_id)
        except ModelVersion.DoesNotExist:
            return Response({"error": "Model version not found"}, status=404)

        data_samples = request.data.get("data_samples", [])
        if not isinstance(data_samples, list) or len(data_samples) == 0:
            return Response({"error": "data_samples must be a non-empty JSON array"}, status=400)

        def _is_number(value):
            return isinstance(value, (int, float))

        def _normalize_sample(value):
            # Single scalar sample -> keep scalar
            if _is_number(value):
                return float(value)
            # Vector sample -> list[float]
            if isinstance(value, list):
                if not value:
                    raise ValueError("Empty sample vectors are not allowed.")
                if not all(_is_number(v) for v in value):
                    raise ValueError("All values in sample vectors must be numeric.")
                return [float(v) for v in value]
            raise ValueError("Each sample must be a number or a list of numbers.")

        try:
            inserted = 0
            # If the whole payload is a numeric vector, store it as one row.
            if all(_is_number(v) for v in data_samples):
                Samples.objects.create(
                    model_version=model_version,
                    data=[float(v) for v in data_samples],
                )
                inserted = 1
            else:
                rows = []
                for sample_data in data_samples:
                    rows.append(
                        Samples(model_version=model_version, data=_normalize_sample(sample_data))
                    )
                Samples.objects.bulk_create(rows)
                inserted = len(rows)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        return Response({"status": "samples saved", "inserted": inserted}, status=201)
        
class DataDriftAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, model_version_id):
        drifts = DataDrift.objects.filter(model_version=model_version_id).order_by("-scanned_at")
        serializer = DataDriftSerializer(drifts, many=True)
        return Response(serializer.data, status=200)

    def post(self, request, model_version_id):
        try:
            model_version = ModelVersion.objects.get(id=model_version_id)
        except ModelVersion.DoesNotExist:
            return Response({"error": "Model version not found"}, status=404)

        baseline_data = model_version.sample_data
        sample_rows = list(Samples.objects.filter(model_version=model_version).order_by("created_at")[:400])

        # Preferred mode: baseline from model_version.sample_data, current from recent samples.
        # Fallback mode: when sample_data is missing, split collected samples into baseline/current windows.
        if baseline_data:
            current_data = []
            for sample in sample_rows[-200:]:
                value = sample.data
                if isinstance(value, list):
                    current_data.extend(value)
                else:
                    current_data.append(value)
            baseline_array = np.array(baseline_data, dtype=float).flatten()
            current_array = np.array(current_data, dtype=float).flatten()
        else:
            flattened = []
            for sample in sample_rows:
                value = sample.data
                if isinstance(value, list):
                    flattened.extend(value)
                else:
                    flattened.append(value)

            if len(flattened) < 20:
                return Response(
                    {"error": "Insufficient data for drift detection. Add baseline sample_data or at least 20 samples."},
                    status=400,
                )

            mid = len(flattened) // 2
            baseline_array = np.array(flattened[:mid], dtype=float).flatten()
            current_array = np.array(flattened[mid:], dtype=float).flatten()

        if baseline_array.size == 0 or current_array.size == 0:
            return Response({"error": "No numeric data available for drift detection."}, status=400)

        try:
            thresholds = {
                "kl_divergence": float(request.data.get("kl_threshold", 0.25)),
                "wasserstein_distance": float(request.data.get("wasserstein_threshold", 0.2)),
                "ks_statistic": float(request.data.get("ks_threshold", 0.3)),
                "chi_square": float(request.data.get("chi_square_threshold", 10.0)),
            }
        except (TypeError, ValueError):
            return Response({"error": "Threshold values must be numeric."}, status=400)

        kl_divergence = float(calculate_kl_divergence(baseline_array, current_array))
        wasserstein_distance = float(calculate_wasserstein_distance(baseline_array, current_array))
        ks_statistic = float(calculate_ks_statistic(baseline_array, current_array))
        chi_square = float(calculate_chi_square(baseline_array, current_array))
        drift_results = {
            "kl_divergence": kl_divergence,
            "wasserstein_distance": wasserstein_distance,
            "ks_statistic": ks_statistic,
            "chi_square": chi_square,
        }
        drift_detected = (
            kl_divergence > thresholds["kl_divergence"]
            or wasserstein_distance > thresholds["wasserstein_distance"]
            or ks_statistic > thresholds["ks_statistic"]
            or chi_square > thresholds["chi_square"]
        )

        drift, _ = DataDrift.objects.update_or_create(
            model_version=model_version,
            defaults={
                "kl_divergence": kl_divergence,
                "wasserstein_distance": wasserstein_distance,
                "ks_statistic": ks_statistic,
                "chi_square": chi_square,
                "results": drift_results,
                "sample_count": int(current_array.size),
            },
        )
        return Response(
            {
                **DataDriftSerializer(drift).data,
                "thresholds": thresholds,
                "drift_detected": drift_detected,
            },
            status=200,
        )
