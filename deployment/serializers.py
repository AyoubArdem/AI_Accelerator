from django.conf import settings
from rest_framework import serializers
from .models import Deployment, ModelVersion, Projet

class ProjetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projet
        fields = ['id', 'owner', 'name', 'description', 'created_at', 'updated_at']

    def validate_owner(self, value):
        if not value:
            raise serializers.ValidationError("Owner field cannot be empty.")
        if value != settings.AUTH_USER_MODEL:
            raise serializers.ValidationError("Owner must be a valid user that you have registered.")
        return value


class ModelVersionSerializer(serializers.ModelSerializer):
    projet = ProjetSerializer(read_only=True)
    class Meta:
        model = ModelVersion
        fields = ['id', 'projet', 'description', 'field_file', 'created_at', 'updated_at', 'deployed']

    def validate_field_file(self, value):
        if not value.name.endswith(('.pkl', '.joblib', '.h5', '.pt')):
            raise serializers.ValidationError("Unsupported file type. Please upload a valid model file.")
        return value
    def validate_projet(self, value):
        if not Projet.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("The specified project does not exist.")
        return value
    
   
class DeploymentSerializer(serializers.ModelSerializer):
    model_version_info = ModelVersionSerializer(source="model_version", read_only=True)

    class Meta:
        model = Deployment
        fields = [
            "id",
            "project",
            "model_version",
            "model_version_info",
            "status",
            "port",
            "server_ip",
            "endpoint_url",
            "docker_container_id",
            "logs",
            "created_at",
            "updated_at"
        ]

        read_only_fields = [
            "server_ip",
            "status",
            "endpoint_url",
            "docker_container_id",
            "logs",
            "created_at",
            "updated_at"
        ]
        

    


        def validate_port(self,value):
            if value.port < 1024 or value.port > 65000:
                    raise serializers.ValidationError("the port must be between 1024 and 65000")
            
            if Deployment.objects.filter(port=value, status="active").exists():
                    raise serializers.ValidationError("This port is already used by another active deployment.")
            return value

       