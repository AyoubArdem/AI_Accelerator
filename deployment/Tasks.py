import subprocess
import os
import shutil
from django.conf import settings
from celery import shared_task
from deployment.models import Deployment 
from governance.utils import LogAction

@shared_task(bind=True, max_retries=3, soft_time_limit=300, time_limit=400)
def deploy_model_task(self, deployment_id):
    try:
        deploy = Deployment.objects.get(id=deployment_id)
        model_path = deploy.model_version.path 

       
        deploy.status = 'deploying'
        deploy.save()

        
        runtime_folder = f'/temp/deploy/{deployment_id}'
        os.makedirs(runtime_folder, exist_ok=True)

        
        allowed_files = ["requirements.txt", "fastapi.py", "Dockerfile"]
        for file in allowed_files:
            shutil.copy(
                os.path.join(settings.DEPLOYEMENT_RUNTIME_PATH, file),
                runtime_folder
            )

        
        shutil.copy(model_path, f"{runtime_folder}/model.pkl")

        
        image_name = f"model_deploy_{deploy.id}"
        subprocess.run(
            ["docker", "build", "--no-cache", "--pull", "-t", image_name, runtime_folder],
            check=True
        )

     
        run_cmd = [
            "docker", "run", "-d",
            "--cpus=1",
            "--memory=1g",
            "--network=none",
            "--read-only",
            "-p", f"{deploy.port}:8000",
            "--security-opt=no-new-privileges",
            image_name
        ]
        container_id = subprocess.check_output(run_cmd).decode().strip()

        
        deploy.docker_container_id = container_id
        deploy.endpoint_url = f"http://localhost:{deploy.port}/predict"
        deploy.status = "active"
        deploy.save()

        if deploy.user.role == "admin": 
                role_permissions = { "role": "admin", "permissions": [ "deployment:*", "monitoring:*", "governance:*", "audit:read" ] }

        elif deploy.user.role == "engineer":
            role_permissions = { "role": "engineer", "permissions": [ "deployment:read", "deployment:write", "monitoring:read" ] }

        else: role_permissions = { "role": "auditor", "permissions": [ "audit:read" ] }

        meta_data = {
            "role_permissions": [
                role_permissions
            ], 
            "deployment": [
              {
                "id": deploy.id,
                "name": deploy.name,
                "port": deploy.port,
                "status": deploy.status
               }
            ],
            "monitoring": {
                "enabled": True,
                
            }
        }
        LogAction(
            user=deploy.user,
            action="DEPLOY",
            description=f"Deployment started for model version {deploy.model_version.name}",
            metadata=meta_data
        ).save()

        from monitoring.Tasks import start_monitor_agent
        start_monitor_agent.delay(deployment_id)
        return {"status": "success"}

    except Exception as e:
        deploy.status = "failed"
        deploy.logs = str(e)
        deploy.save()
        self.retry(exc=e, countdown=5)   

