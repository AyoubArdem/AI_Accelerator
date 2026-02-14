from django.urls import path

from .views import (
    DeploymentStatsAPIView,
    DeploymentRecordsAPIView,
    DeploymentAlertsAPIView,
    DeploymentHealthReportAPIView,
    DeploymentCostIntelligenceAPIView,
    ReceiveMetricsAPIView,
    ResolveAlertAPIView,
    GetSamplesAPIView,
    DataDriftAPIView
)

urlpatterns = [
    path("deployments/<int:deployment_id>/stats/", DeploymentStatsAPIView.as_view(), name="deployment-stats"),
    path("deployments/<int:deployment_id>/records/", DeploymentRecordsAPIView.as_view(), name="deployment-records"),
    path("deployments/<int:deployment_id>/alerts/", DeploymentAlertsAPIView.as_view(), name="deployment-alerts"),
    path("deployments/<int:deployment_id>/health-report/", DeploymentHealthReportAPIView.as_view(), name="deployment-health-report"),
    path("deployments/<int:deployment_id>/cost-intelligence/", DeploymentCostIntelligenceAPIView.as_view(), name="deployment-cost-intelligence"),
    path("deployments/<int:deployment_id>/metrics/", ReceiveMetricsAPIView.as_view(), name="deployment-metrics"),
    path("alerts/<uuid:alert_id>/resolve/",ResolveAlertAPIView.as_view(), name="resolve-alert"),
    path("deployments/samples/", GetSamplesAPIView.as_view(), name="samples"),
    path("drifts/<int:model_version_id>/", DataDriftAPIView.as_view(), name="data-drifts"),
]

