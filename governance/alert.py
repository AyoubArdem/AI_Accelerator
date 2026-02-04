from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PolicyViolation
from django.core.mail import send_mail
from .models import Alert


@receiver(post_save,sender=PolicyViolation)
def create_alert(sender,instance,**kwargs):
    if instance:
        Alert.objects.create(
            policy_violation=instance,
            message=f"You have a problem with a {instance.severity} level: {instance.violation_type}, check the policy.",
            sent=False
        )
        
        # Assuming policy has user with email
        if instance.policy and instance.policy.user.email:
            send_mail(
                subject="Policy Violation Alert",
                message=f"A policy violation has occurred:\n\nPolicy: {instance.policy}\nDeployment: {instance.deployment}\nViolation: {instance.violation_type}",
                from_email="admin@aiac.com",
                recipient_list=[instance.policy.user.email]
            )