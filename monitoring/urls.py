from django.urls import path

from .views import (
    DeploymentStatsAPIView,
    DeploymentAlertsAPIView,
    ReceiveMetricsAPIView,
    ResolveAlertAPIView,
    GetSamplesAPIView,
    DataDriftAPIView
)

urlpatterns = [
    path("deployments/<int:deployment_id>/stats/", DeploymentStatsAPIView.as_view(), name="deployment-stats"),
    path("deployments/<int:deployment_id>/records/", DeploymentAlertsAPIView.as_view(), name="deployment-records"),
    path("deployments/<int:deployment_id>/alerts/", ReceiveMetricsAPIView.as_view(), name="deployment-alerts"),
    path("alerts/<uuid:alert_id>/resolve/",ResolveAlertAPIView.as_view(), name="resolve-alert"),
    path("deployments/samples/", GetSamplesAPIView.as_view(), name="samples"),
    path("drifts/<int:model_version_id>/", DataDriftAPIView.as_view(), name="data-drifts"),
]

