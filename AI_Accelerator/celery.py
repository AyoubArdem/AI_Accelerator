from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE","AI_Accelerator.settings")

app = Celery('AI_Accelerator')

app.config_from_object('django.confg:settings',namespace='CELERY')

app.autodiscover_tasks()

