from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .utils import send_activation_email, send_password_reset_email
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    AdminUserUpdateSerializer,
    AdminPasswordResetSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .tokens import account_activation_token, password_reset_token

User = get_user_model()


def _is_admin(user) -> bool:
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False) or getattr(user, "role", "") == "admin")


def _require_admin(request):
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    return None


class RegisterUserView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            activation_link = send_activation_email(user, request)
            payload = {"message": "Account created successfully. Please check your link to activate your account."}
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


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            user = User.objects.filter(email=email).first()
            reset_link = None
            if user:
                reset_link = send_password_reset_email(user, request)
            # Always return success to avoid account enumeration.
            payload = {"message": "If the email exists, a reset link has been sent."}
            if settings.DEBUG and reset_link:
                payload["reset_link"] = reset_link
            return Response(payload, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def _wants_html(self, request) -> bool:
        accept = (request.headers.get("Accept") or "").lower()
        return "text/html" in accept

    def get(self, request, uid, token):
        user = get_object_or_404(User, pk=uid)
        if not password_reset_token.check_token(user, token):
            message = "This reset link is invalid or has expired."
            if self._wants_html(request):
                return render(
                    request,
                    "users/password_reset_result.html",
                    {
                        "title": "Reset Link Invalid",
                        "message": message,
                        "status_label": "Failed",
                        "is_success": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        if self._wants_html(request):
            return render(
                request,
                "users/password_reset_form.html",
                {
                    "title": "Reset Your Password",
                    "message": "Set a new password for your account.",
                    "uid": uid,
                    "token": token,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Valid reset link. Submit new password via POST."},
            status=status.HTTP_200_OK,
        )

    def post(self, request, uid, token):
        user = get_object_or_404(User, pk=uid)
        if not password_reset_token.check_token(user, token):
            message = "This reset link is invalid or has expired."
            if self._wants_html(request):
                return render(
                    request,
                    "users/password_reset_result.html",
                    {
                        "title": "Reset Failed",
                        "message": message,
                        "status_label": "Failed",
                        "is_success": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user.set_password(serializer.validated_data["password"])
            user.save(update_fields=["password"])
            message = "Password reset successful. You can now log in."
            if self._wants_html(request):
                return render(
                    request,
                    "users/password_reset_result.html",
                    {
                        "title": "Password Reset",
                        "message": message,
                        "status_label": "Success",
                        "is_success": True,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response({"message": message}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        users = User.objects.all().order_by("id")
        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    def patch(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminUserActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"message": "User activated."}, status=status.HTTP_200_OK)


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"message": "User deactivated."}, status=status.HTTP_200_OK)


class AdminUserSoftDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"message": "User soft-deleted (deactivated)."}, status=status.HTTP_200_OK)


class AdminUserPromoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        user.role = "admin"
        user.is_staff = True
        user.save(update_fields=["role", "is_staff"])
        return Response({"message": "User promoted to admin."}, status=status.HTTP_200_OK)


class AdminUserDemoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        user.role = "client"
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["role", "is_staff", "is_superuser"])
        return Response({"message": "User demoted to client."}, status=status.HTTP_200_OK)


class AdminUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        forbidden = _require_admin(request)
        if forbidden:
            return forbidden
        user = get_object_or_404(User, pk=user_id)
        serializer = AdminPasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            user.set_password(serializer.validated_data["password"])
            user.save(update_fields=["password"])
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
