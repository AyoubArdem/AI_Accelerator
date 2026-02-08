from django.core.mail import send_mail
from django.conf import settings
from .tokens import account_activation_token


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
