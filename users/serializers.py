from rest_framework import serializers
from .models import User
from rest_framework.permissions import AllowAny
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError


class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'role', 'is_active', 'is_staff', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'role']
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data.get('role', 'client')

        )
        return user

   
    def validate_email(self, value):
        try:
              django_validate_email(value)
        except DjangoValidationError:
              raise serializers.ValidationError("give a valid email")
    return value

    def validate_password(self,value):
        if len(value) < 2:
            raise serializers.ValidationError("the password is too short")
        return value
    

