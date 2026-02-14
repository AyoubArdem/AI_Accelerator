from django.conf import settings
from rest_framework import serializers
from .models import Deployment, ModelVersion, Projet

class ProjetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projet
        fields = ['id', 'owner', 'name', 'description', 'created_at', 'updated_at']


class ModelVersionSerializer(serializers.ModelSerializer):
    projet = serializers.PrimaryKeyRelatedField(queryset=Projet.objects.all(), required=False)
    project_id = serializers.IntegerField(write_only=True, required=False)
    project = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = ModelVersion
        fields = ['id', 'projet', 'project_id', 'project', 'description', 'field_file', 'created_at', 'updated_at', 'deployed']

    def validate(self, attrs):
        if not attrs.get("projet") and not attrs.get("project_id") and not attrs.get("project"):
            raise serializers.ValidationError({"projet": "This field is required."})
        return attrs

    def create(self, validated_data):
        if not validated_data.get("projet"):
            project_id = validated_data.pop("project_id", None) or validated_data.pop("project", None)
            if project_id is not None:
                validated_data["projet"] = Projet.objects.get(pk=project_id)
        return super().create(validated_data)

    def validate_field_file(self, value):
        if not value.name.endswith(('.pkl', '.joblib', '.h5', '.pt')):
            raise serializers.ValidationError("Unsupported file type. Please upload a valid model file.")
        return value
    

    
class DeploymentSerializer(serializers.ModelSerializer):
    #model_version_info = ModelVersionSerializer(source="model_version", read_only=True)
    runtime_urls = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = [
            "id",
            "user",
            "docker_container_id",
            "model_version",
            "deployed_at",
            "port",
            "endpoint_url",
            "runtime_urls",
            "status",
            "logs",
        ]
        read_only_fields = [
            "id",
            "status",
            "endpoint_url",
            "docker_container_id",
            "logs",
            "deployed_at",
        ]
        
    def validate_port(self, value):
        if value < 1024 or value > 65000:
            raise serializers.ValidationError("The port must be between 1024 and 65000")

        if Deployment.objects.filter(port=value, status="ACTIVE").exists():
            raise serializers.ValidationError("This port is already used by another active deployment.")
        return value

    def get_runtime_urls(self, obj):
        if obj and obj.port:
            base_url = f"http://127.0.0.1:{obj.port}"
        elif obj and obj.endpoint_url:
            base_url = str(obj.endpoint_url).replace("/predict", "")
        else:
            base_url = ""
        if not base_url:
            return {}
        return {
            "base_url": base_url,
            "ui_page": f"{base_url}/ui",
            "ui_docs": f"{base_url}/docs",
            "ui_redoc": f"{base_url}/redoc",
            "health": f"{base_url}/health",
            "predict": f"{base_url}/predict",
        }

       
