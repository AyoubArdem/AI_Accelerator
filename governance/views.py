from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated 
from .serializers import PolicySerializer, PolicyAssignmentSerializer, AuditLogSerializer
from .models import Policy, PolicyAssignment, AuditLog
# Create your views here.

class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class PolicyAssignmentViewSet(viewsets.ModelViewSet):
    queryset = PolicyAssignment.objects.all()
    serializer_class = PolicyAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(applied_by=self.request.user)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]