from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PolicyViolation,Alert


@receiver(post_save,sender=PolicyViolation)
def create_alert(sender,instance,**kwargs):
    if instance:
        Alert.objects.create(
            policy_violation = sender,
            message = "you have a problem in {sender.policy.service} with a {sender.severity} level : {sender.violation_type} , check the policy --> {sender.policy.metadata}",
            sent = True
        )
    