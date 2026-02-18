from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .utils import send_activation_email
from .serializers import RegisterSerializer, UserSerializer
from .tokens import account_activation_token

User = get_user_model()


class RegisterUserView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            activation_link = send_activation_email(user, request)
            payload = {"message": "Account created successfully. Please check your email to activate your account."}
            if settings.DEBUG:
                payload["activation_link"] = activation_link
            return Response(payload, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActivateAccountView(APIView):
    permission_classes = [AllowAny]

    def _wants_html(self, request) -> bool:
        accept = (request.headers.get("Accept") or "").lower()
        return "text/html" in accept

    def get(self, request, uid, token):
        user = get_object_or_404(User, pk=uid)

        if user.is_active:
            message = "Your account is already active. You can log in now."
            payload = {"message": message}
            if self._wants_html(request):
                return render(
                    request,
                    "users/activation_result.html",
                    {
                        "title": "Account Already Active",
                        "message": message,
                        "status_label": "Already Active",
                        "is_success": True,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(payload, status=status.HTTP_200_OK)

        if account_activation_token.check_token(user, token):
            user.is_active = True
            user.save()
            message = "Account activated successfully. You can now sign in to AIAC."
            payload = {"message": message}
            if self._wants_html(request):
                return render(
                    request,
                    "users/activation_result.html",
                    {
                        "title": "Activation Successful",
                        "message": message,
                        "status_label": "Success",
                        "is_success": True,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(payload, status=status.HTTP_200_OK)

        message = "This activation link is invalid or has expired. Please register again or request a new activation email."
        payload = {"error": message}
        if self._wants_html(request):
            return render(
                request,
                "users/activation_result.html",
                {
                    "title": "Activation Failed",
                    "message": message,
                    "status_label": "Failed",
                    "is_success": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, email=email, password=password)
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
            }, status=status.HTTP_200_OK)
        return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
