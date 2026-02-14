from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PolicyViolation
from django.core.mail import send_mail
from .models import Alert
import logging

logger = logging.getLogger(__name__)


@receiver(post_save,sender=PolicyViolation)
def create_alert(sender, instance, created, **kwargs):
    if not created:
        return

    alert = Alert.objects.create(
        policy_violation=instance,
        message=f"You have a problem with a {instance.severity} level: {instance.violation_type}, check the policy.",
        sent=False,
    )

    # Keep API flow resilient if email backend is unavailable.
    if instance.policy and instance.policy.user.email:
        try:
            send_mail(
                subject="Policy Violation Alert",
                message=f"A policy violation has occurred:\n\nPolicy: {instance.policy}\nDeployment: {instance.deployment}\nViolation: {instance.violation_type}",
                from_email="admin@aiac.com",
                recipient_list=[instance.policy.user.email],
            )
            alert.sent = True
            alert.save(update_fields=["sent"])
        except Exception as exc:
            logger.warning(
                "Failed to send policy violation email alert for violation_id=%s: %s",
                instance.id,
                exc,
            )

       
