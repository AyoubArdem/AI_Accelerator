from django.shortcuts import render,get_object_or_404
from .serializers import UserSerializer, RegisterSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework.permissions import AllowAny,IsAuthenticated
from .utils import send_activation_email
from .tokens import account_activation_token
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
# Create your views here.

class RegisterUserView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            send_activation_email(User, request)
            return Response(   
                {"message": "Account created successfully. Please check your email to activate your account."},status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

class ActivateAccountView(APIView):
    permission_classes = [AllowAny]

    def get(self,request,uid,token):
        user = get_object_or_404(user, pk=uid)
        if account_activation_token.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({"message": "Account activated successfully!"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid activation link or expired token."}, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self,request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = get_object_or_404(User, email=email)
        user = authenticate(request,email=email,password=password)
        if user is not None:
            if not user.is_active:
                return Response({"error": "Account is not activated."}, status=status.HTTP_403_FORBIDDEN)
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                "user": {
                    "email": user.email,
                    "username": user.username,
                    "role": user.role
                }
            },status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except token.DoesNotExist as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)