from django.urls import path
from .views import (
    RegisterUserView,
    ActivateAccountView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    AdminUserListView,
    AdminUserDetailView,
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserPromoteView,
    AdminUserDemoteView,
    AdminUserResetPasswordView,
    AdminUserSoftDeleteView,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("activate/<int:uid>/<str:token>/", ActivateAccountView.as_view(), name="activate"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password-reset/confirm/<int:uid>/<str:token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Admin user management
    path("admin/users/", AdminUserListView.as_view(), name="admin_users_list"),
    path("admin/users/<int:user_id>/", AdminUserDetailView.as_view(), name="admin_user_detail"),
    path("admin/users/<int:user_id>/activate/", AdminUserActivateView.as_view(), name="admin_user_activate"),
    path("admin/users/<int:user_id>/deactivate/", AdminUserDeactivateView.as_view(), name="admin_user_deactivate"),
    path("admin/users/<int:user_id>/soft-delete/", AdminUserSoftDeleteView.as_view(), name="admin_user_soft_delete"),
    path("admin/users/<int:user_id>/promote/", AdminUserPromoteView.as_view(), name="admin_user_promote"),
    path("admin/users/<int:user_id>/demote/", AdminUserDemoteView.as_view(), name="admin_user_demote"),
    path("admin/users/<int:user_id>/reset-password/", AdminUserResetPasswordView.as_view(), name="admin_user_reset_password"),

    # API schema docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
