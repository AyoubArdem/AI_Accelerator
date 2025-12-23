from rest_framework.routers import DefaultRouter
from .views import PolicyViewSet, PolicyAssignmentViewSet, AuditLogViewSet

urlpatterns = []

router = DefaultRouter()
router.register(r"policies", PolicyViewSet)
router.register(r"policy-assignments", PolicyAssignmentViewSet)
router.register(r"audit-logs", AuditLogViewSet)

urlpatterns += router.urls
