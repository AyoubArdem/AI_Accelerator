from django.core.mail import send_mail
from django.conf import settings

def send_activation_email(user, request):
    from .tokens import account_activation_token
    token = account_activation_token.make_token(user)
    uid = user.id
    activation_link = f"http://{request.get_host()}/api/users/activate/{uid}/{token}/"
    subject = "Activate your AI Accelerator account"
    message = f"Hi {user.username},\n\nPlease click the link below to activate your account:\n{activation_link}\n\nThank you for joining AI Accelerator!"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )