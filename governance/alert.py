from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PolicyViolation
from django.core.mail import send_mail
from .models import Alert


@receiver(post_save,sender=PolicyViolation)
def create_alert(sender,instance,**kwargs):
    if instance:
        Alert.objects.create(
            policy_violation = sender,
            message = "you have a problem in {sender.policy.service} with a {sender.severity} level : {sender.violation_type} , check the policy --> {sender.policy.metadata}",
            sent = True
        )
        
        send_mail(
            subject="Policy Violation Alert",
            message=f"A policy violation has occurred:\n\nPolicy: {instance.policy}\nDeployment: {instance.deployment}",
            from_email="admin@aiac.com",
            recipient_list=["{instance.user.email}"]
        )