from django.shortcuts import render
from rest_framework import viewsets , generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated 
from .serializers import PolicySerializer, PolicyAssignmentSerializer, AuditLogSerializer, ViolationSerializer , AlertSerializer
from rest_framework.response import Response
from .models import Policy, PolicyAssignment, AuditLog ,PolicyViolation , Alert
from .permission import IsPolicyAdmin
# Create your views here.

class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class PolicyDelete(generics.DestroyAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [IsPolicyAdmin]

class PolicyAssignmentViewSet(viewsets.ModelViewSet):
    queryset = PolicyAssignment.objects.all()
    serializer_class = PolicyAssignmentSerializer
    permission_classes = [IsPolicyAdmin]

    def perform_create(self, serializer):
        serializer.save(applied_by=self.request.user)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsPolicyAdmin]

class PolicyViolationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PolicyViolation.objects.all()
    serializer_class = ViolationSerializer
    permission_classes = [IsPolicyAdmin]

    

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsPolicyAdmin]