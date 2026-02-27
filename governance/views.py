from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .serializers import PolicySerializer, PolicyAssignmentSerializer, AuditLogSerializer, ViolationSerializer, AlertSerializer
from rest_framework.response import Response
from rest_framework import status
from .models import Policy, PolicyAssignment, AuditLog, PolicyViolation, Alert
from .engine import check_violation
from .task import run_policy_engine
from .task import _policy_target, _log_matches_target
from .services import get_policy_insights_for_user


def _is_governance_admin(user):
    return getattr(user, "is_superuser", False) or getattr(user, "role", None) == "admin"


class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_governance_admin(user):
            return Policy.objects.all()
        return Policy.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="insights")
    def insights(self, request):
        policy_raw = request.query_params.get("policy")
        days_raw = request.query_params.get("days", 7)

        policy_id = None
        if policy_raw is not None:
            try:
                policy_id = int(policy_raw)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Query param 'policy' must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            days = max(1, min(int(days_raw), 90))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Query param 'days' must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = get_policy_insights_for_user(
            user=request.user,
            is_admin=_is_governance_admin(request.user),
            policy_id=policy_id,
            days=days,
        )
        return Response(payload)

class PolicyDelete(generics.DestroyAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_governance_admin(user):
            return Policy.objects.all()
        return Policy.objects.filter(user=user)

class PolicyAssignmentViewSet(viewsets.ModelViewSet):
    queryset = PolicyAssignment.objects.all()
    serializer_class = PolicyAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = PolicyAssignment.objects.select_related("policy", "deployment", "applied_by").all().order_by("-applied_at")
        if _is_governance_admin(user):
            return queryset
        return queryset.filter(policy__user=user, deployment__user=user)

    def perform_create(self, serializer):
        serializer.save(applied_by=self.request.user)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = AuditLog.objects.select_related("deployment", "user").all().order_by("-timestamp")
        if not _is_governance_admin(user):
            queryset = queryset.filter(deployment__user=user)
        deployment_id = self.request.query_params.get("deployment")
        if deployment_id:
            queryset = queryset.filter(deployment_id=deployment_id)
        return queryset

class PolicyViolationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PolicyViolation.objects.all()
    serializer_class = ViolationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = PolicyViolation.objects.select_related("deployment", "policy").all().order_by("-created_at")
        if not _is_governance_admin(user):
            queryset = queryset.filter(deployment__user=user)
        deployment_id = self.request.query_params.get("deployment")
        severity = self.request.query_params.get("severity")
        resolved = self.request.query_params.get("resolved")
        if deployment_id:
            queryset = queryset.filter(deployment_id=deployment_id)
        if severity:
            queryset = queryset.filter(severity=severity)
        if resolved in {"true", "false"}:
            queryset = queryset.filter(resolved=(resolved == "true"))
        return queryset

    @action(detail=False, methods=["get"], url_path="metrics")
    def metrics(self, request):
        queryset = self.get_queryset()
        data = {
            "total_violations": queryset.count(),
            "unresolved_violations": queryset.filter(resolved=False).count(),
            "resolved_violations": queryset.filter(resolved=True).count(),
            "high_severity_violations": queryset.filter(severity="high").count(),
            "medium_severity_violations": queryset.filter(severity="medium").count(),
            "low_severity_violations": queryset.filter(severity="low").count(),
        }
        return Response(data)

    @action(detail=False, methods=["post"], url_path="resolve-all")
    def resolve_all(self, request):
        deployment_id_raw = request.data.get("deployment")
        policy_id_raw = request.data.get("policy")

        deployment_id = None
        policy_id = None
        if deployment_id_raw not in (None, ""):
            try:
                deployment_id = int(deployment_id_raw)
            except (TypeError, ValueError):
                return Response({"detail": "deployment must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if policy_id_raw not in (None, ""):
            try:
                policy_id = int(policy_id_raw)
            except (TypeError, ValueError):
                return Response({"detail": "policy must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = PolicyViolation.objects.select_related("deployment").filter(resolved=False)
        if deployment_id is not None:
            queryset = queryset.filter(deployment_id=deployment_id)
        if policy_id is not None:
            queryset = queryset.filter(policy_id=policy_id)

        if not _is_governance_admin(request.user):
            queryset = queryset.filter(deployment__user=request.user)

        to_update = list(queryset.values_list("id", flat=True))
        if not to_update:
            return Response(
                {"message": "No unresolved violations matched the filter.", "resolved_count": 0},
                status=status.HTTP_200_OK,
            )

        updated = queryset.update(resolved=True)
        return Response(
            {
                "message": f"Resolved {updated} violation(s).",
                "resolved_count": updated,
                "violation_ids": to_update,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        violation = self.get_object()
        if not _is_governance_admin(request.user) and violation.deployment.user_id != request.user.id:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        if violation.resolved:
            return Response(
                {"message": "Violation is already resolved.", "violation_id": violation.id},
                status=status.HTTP_200_OK,
            )
        violation.resolved = True
        violation.save(update_fields=["resolved"])
        return Response(
            {"message": "Violation resolved successfully.", "violation_id": violation.id},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        violation = self.get_object()
        if not _is_governance_admin(request.user) and violation.deployment.user_id != request.user.id:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        if not violation.resolved:
            return Response(
                {"message": "Violation is already open.", "violation_id": violation.id},
                status=status.HTTP_200_OK,
            )
        violation.resolved = False
        violation.save(update_fields=["resolved"])
        return Response(
            {"message": "Violation reopened successfully.", "violation_id": violation.id},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="run-engine")
    def run_engine(self, request):
        task = run_policy_engine.delay()
        return Response(
            {
                "message": "Policy engine triggered successfully.",
                "task_id": str(task.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path="debug-engine")
    def debug_engine(self, request):
        policy_id = request.query_params.get("policy")
        if not policy_id:
            return Response(
                {"detail": "Query param 'policy' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            policy_id = int(policy_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Query param 'policy' must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        policy_qs = Policy.objects.filter(id=policy_id)
        if not _is_governance_admin(user):
            policy_qs = policy_qs.filter(user=user)
        policy = policy_qs.first()
        if not policy:
            return Response(
                {"detail": "Policy not found or access denied."},
                status=status.HTTP_404_NOT_FOUND,
            )

        deployment_id = request.query_params.get("deployment")
        if deployment_id:
            try:
                deployment_id = int(deployment_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Query param 'deployment' must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        limit_raw = request.query_params.get("limit", 50)
        try:
            limit = max(1, min(int(limit_raw), 200))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Query param 'limit' must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment_qs = PolicyAssignment.objects.filter(policy=policy)
        if deployment_id:
            assignment_qs = assignment_qs.filter(deployment_id=deployment_id)
        if not _is_governance_admin(user):
            assignment_qs = assignment_qs.filter(deployment__user=user)

        assigned_deployment_ids = list(assignment_qs.values_list("deployment_id", flat=True))
        target = _policy_target(policy)

        if not assigned_deployment_ids:
            return Response(
                {
                    "policy_id": policy.id,
                    "policy_name": policy.name,
                    "target": target,
                    "assigned_deployments": [],
                    "summary": {
                        "evaluated_logs": 0,
                        "scope_skipped": 0,
                        "matched": 0,
                        "violations": 0,
                    },
                    "results": [],
                    "note": "Policy has no matching assignments for this filter.",
                }
            )

        logs_qs = AuditLog.objects.filter(deployment_id__in=assigned_deployment_ids).order_by("-timestamp")[:limit]
        results = []
        scope_skipped = 0
        matched = 0
        violations = 0

        for log in logs_qs:
            if not _log_matches_target(log, target):
                scope_skipped += 1
                results.append(
                    {
                        "log_id": str(log.id),
                        "deployment_id": log.deployment_id,
                        "action": log.action,
                        "service": log.service,
                        "severity": log.severity,
                        "timestamp": log.timestamp,
                        "status": "skipped_scope",
                        "reason": f"log target does not match policy target '{target}'",
                    }
                )
                continue

            violated = check_violation(log.metadata, policy.rules)
            if violated:
                violations += 1
                status_name = "violation"
                reason = "metadata mismatches policy rules"
            else:
                matched += 1
                status_name = "matched"
                reason = "metadata satisfies policy rules"

            results.append(
                {
                    "log_id": str(log.id),
                    "deployment_id": log.deployment_id,
                    "action": log.action,
                    "service": log.service,
                    "severity": log.severity,
                    "timestamp": log.timestamp,
                    "status": status_name,
                    "reason": reason,
                }
            )

        return Response(
            {
                "policy_id": policy.id,
                "policy_name": policy.name,
                "target": target,
                "assigned_deployments": assigned_deployment_ids,
                "summary": {
                    "evaluated_logs": len(results),
                    "scope_skipped": scope_skipped,
                    "matched": matched,
                    "violations": violations,
                },
                "results": results,
            }
        )


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Alert.objects.select_related("policy_violation", "policy_violation__deployment").all().order_by("-timestamp")
        if not _is_governance_admin(user):
            queryset = queryset.filter(policy_violation__deployment__user=user)
        deployment_id = self.request.query_params.get("deployment")
        sent = self.request.query_params.get("sent")
        if deployment_id:
            queryset = queryset.filter(policy_violation__deployment_id=deployment_id)
        if sent in {"true", "false"}:
            queryset = queryset.filter(sent=(sent == "true"))
        return queryset
