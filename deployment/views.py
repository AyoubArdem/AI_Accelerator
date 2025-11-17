from django.shortcuts import render
from .models import Deployment, ModelVersion, Projet
from .serializers import DeploymentSerializer, ModelVersionSerializer, ProjetSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

# Create your views here.

class ProjectViewSet(viewsets.ModelViewset):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [IsAuthenticated]

class ModelVersionViewset(viewsets.ModelViewset):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]

class DeploymentViewset(viewsets.ModelViewset):
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(status=Deployment.StatusChoices.PENDING)
        

