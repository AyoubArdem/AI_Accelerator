from django.shortcuts import render
from rest_framework import generics,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from deployment.models import Deployment, ModelVersion
from rest_framework.response import Response
from .models import (
    DataDrift,
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

class DeploymentStatsAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeploymentStatsSerializer
    lookup_field = "deployment_id"

    def get_queryset(self):
        return DeploymentStats.objects.all()
    


class DeploymentAlertsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeploymentAlertSerializer

    def get_queryset(self):
        deployment_id = self.kwargs["deployment_id"]
        return DeploymentAlert.objects.filter(deployment=deployment_id).order_by("-created_at")
    



class ReceiveMetricsAPIView(APIView):


    def post(self, request):
        data = request.data
        deployment_id = data.get("deployment_id")

        
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

    def post(self, request, model_version_id):
        try:
            model_version = ModelVersion.objects.get(id=model_version_id)
        except ModelVersion.DoesNotExist:
            return Response({"error": "Model version not found"}, status=404)
        if request.method == 'POST':
            data_samples = request.data.get('data_samples', [])
            for sample_data in data_samples:
                Samples.objects.create(
                    model_version=model_version,
                    data=sample_data
                )
            return Response({"status": "samples saved"}, status=201)
        
class DataDriftAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DataDriftSerializer

    def get_queryset(self):
        model_version_id = self.kwargs["model_version_id"]
        return DataDrift.objects.filter(model_version=model_version_id).order_by("-scanned_at")