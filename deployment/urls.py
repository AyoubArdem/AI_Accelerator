from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views import (
    ProjectViewSet,
    ModelVersionViewset,
    CreateDeploymentView,
    ListDeploymentsView,
    DeploymentDetailView,
    RedeployView,
    StopDeploymentView,
    DeleteDeploymentView,
    ModelVersionDelete,
    ProjectDelete,
)

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path("projects/", ProjectViewSet.as_view()),
    path("projects/<int:pk>/delete/", ProjectDelete.as_view()),
    path("model-versions/", ModelVersionViewset.as_view()),
    path("model-versions/<int:pk>/delete/", ModelVersionDelete.as_view()),
    path("deployments/", CreateDeploymentView.as_view()),
    path("deployments/list/", ListDeploymentsView.as_view()),
    path("deployments/<int:id>/", DeploymentDetailView.as_view()),
    path("deployments/<int:deployment_id>/redeploy/", RedeployView.as_view()),
    path("deployments/<int:deployment_id>/stop/", StopDeploymentView.as_view()),
    path("deployments/<int:deployment_id>/delete/", DeleteDeploymentView.as_view()),

]