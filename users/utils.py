from django.core.mail import send_mail
from django.conf import settings
from .tokens import account_activation_token, password_reset_token


def send_activation_email(user, request):
    token = account_activation_token.make_token(user)
    uid = user.id
    activation_link = f"http://localhost:8000/api/users/activate/{uid}/{token}/"
    subject = "Activate your AI Accelerator account"
    message = (
        f"Hi {user.username},\n\n"
        f"Please click the link below to activate your account:\n{activation_link}\n\n"
        "Thank you for joining AI Accelerator!"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return activation_link


def send_password_reset_email(user, request):
    token = password_reset_token.make_token(user)
    uid = user.id
    reset_link = f"http://localhost:8000/api/users/password-reset/confirm/{uid}/{token}/"
    subject = "Reset your AI Accelerator password"
    message = (
        f"Hi {user.username},\n\n"
        "We received a request to reset your password.\n"
        f"Use the link below to set a new password:\n{reset_link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return reset_link
