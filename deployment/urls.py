from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path("deployments/", CreateDeploymentView.as_view()),
    path("deployments/list/", ListDeploymentsView.as_view()),
    path("deployments/<int:id>/", DeploymentDetailView.as_view()),
    path("deployments/<int:deployment_id>/redeploy/", RedeployView.as_view()),
    path("deployments/<int:deployment_id>/stop/", StopDeploymentView.as_view()),
    path("deployments/<int:deployment_id>/delete/", DeleteDeploymentView.as_view()),

]