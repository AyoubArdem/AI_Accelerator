from rest_framework import serializers
from .models import User
from rest_framework.permissions import AllowAny
#from django.core.validators import validate_email as django_validate_email
#from django.core.exceptions import ValidationError as DjangoValidationError


class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'role', 'is_active', 'is_staff', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'role']
    
    def validate_role(self, value):
        if value == "admin":
            # Allow only the first admin user created via registration.
            existing_admin = User.objects.filter(role="admin").first()
            if existing_admin:
                raise serializers.ValidationError(
                    f"An admin user already exists. Contact {existing_admin.email} to be promoted."
                )
        return value

    def create(self, validated_data):
        role = validated_data.get('role', 'client')
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            role=role,
        )
        if role == "admin":
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        return user

   
    def validate_email(self, value):
        if  not  value or '@' not in value:
              raise serializers.ValidationError("give a valid email")
        return value

    def validate_password(self,value):
        if len(value) < 8:
            raise serializers.ValidationError("the password is too short")
        return value


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["role", "is_active", "is_staff", "is_superuser"]


class AdminPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
   
