from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PolicyViewSet, PolicyAssignmentViewSet, AuditLogViewSet ,  PolicyDelete , AlertViewSet , PolicyViolationViewSet

urlpatterns = [
    path("delete-policy/<int:pk>/", PolicyDelete.as_view(), name="delete-policy")
]

router = DefaultRouter()
router.register(r"policies", PolicyViewSet)
router.register(r"policy-assignments", PolicyAssignmentViewSet)
router.register(r"audit-logs", AuditLogViewSet)
router.register(r"policy-violations", PolicyViolationViewSet, basename='policy-violations')
router.register(r"alerts", AlertViewSet, basename="alerts")

urlpatterns += router.urls
