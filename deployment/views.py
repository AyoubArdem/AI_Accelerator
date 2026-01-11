from django.shortcuts import render
from .models import Deployment, ModelVersion, Projet
from .serializers import DeploymentSerializer, ModelVersionSerializer, ProjetSerializer
from rest_framework import viewsets , generics
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics 
from rest_framework.views import APIView
from rest_framework.response import Response
from .Tasks import deploy_model_task

# Create your views here.

class ProjectViewSet(generics.ListCreateAPIView):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [IsAuthenticated]



class ProjectDelete(generics.RetrieveAPIView):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [IsAuthenticated]

class ModelVersionViewset(generics.ListCreateAPIView):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]

class ModelVersionDelete(generics.RetrieveAPIView):
    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAuthenticated]

class CreateDeploymentView(viewsets.ModelViewset):
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        deployement=serializer.save(status=Deployment.StatusChoices.PENDING)
        deploy_model_task.delay(deployement.id)

class ListDeploymentsView(generics.ListAPIView):
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Deployment.objects.filter(user=self.request.user)


class DeploymentDetailView(generics.ListApiView):
    queryset = Deployment.objects.get(id=id)
    serializer_class =  DeploymentSerializer()
    permission_class = [IsAuthenticated]


class RedeployView(APIView):
    def post(self, request, deployment_id):
        try:
            deploy_model_task.delay(deployment_id)
            return Response({"message": "Redeployment started."})
        except:
            return Response({"error": "Invalid deployment id"}, status=400)


   


class StopDeploymentView(APIView):
    def post(self, request, deployment_id):
        try:
            deployment = Deployment.objects.get(id=deployment_id)

            if not deployment.docker_container_id:
                return Response({"error": "No running container"}, status=400)

            import subprocess

            subprocess.run(
                ["docker", "stop", deployment.docker_container_id],
                check=True
            )

            deployment.status = "Stopped"
            deployment.save()

            return Response({"message": "Deployment stopped"})

        except Exception as e:
            return Response({"error": str(e)}, status=400)



class DeleteDeploymentView(APIView):
    def delete(self, request, deployment_id):
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            import subprocess

            
            if deployment.docker_container_id:
                subprocess.run(["docker", "stop", deployment.docker_container_id], stderr=subprocess.PIPE)

            
            subprocess.run(["docker", "rm", deployment.docker_container_id], stderr=subprocess.PIPE)

    
            image_name = f"deploy_image_{deployment.id}"
            subprocess.run(["docker", "rmi", image_name], stderr=subprocess.PIPE)

            deployment.status = "deleted"
            deployment.save()

            return Response({"message": "Deployment deleted"})

        except Exception as e:
            return Response({"error": str(e)}, status=400)



