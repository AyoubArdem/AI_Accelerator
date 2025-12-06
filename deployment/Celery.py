from celery import Celery
import subprocess
import os
import shutil
from django.conf import settings


@shared_task(bind=True,max_retries=3,soft_time_limit=300,time_limit=400)
def deploy_model_task(self,deployement_id):
    try:
           deploy = Deployment.objects.get(id=deployement_id)
           model_path = Deploy.model_version.field_file

           Deploy.status = 'deploying'
           Deploy.save()
           runTime_folder = f'/temp/deploy/{deployement_id}'
           os.makedirs(runTime_folder,exist_ok=True)
           allowed_files=["requirements.txt","fastapi.py","DockerFile"]
           for file in allowed_files:
                 shutil.copy(os.path.join(settings.DEPLOYEMENT_RUNTIME_PATH,file),runTime_folder)
            shtil.copy(model_path, f"{runTime_folder}/model.pkl")
            image_name = f"model_deploy_{Deploy.id}"

            subprocess.run(
                        ["docker", "build", "--no-cache","--pull", "-t", image_name, runtime_folder],
                        check=True
            )
            run_cmd = [
            "docker", "run", "-d",
            "--cpus=1",
            "--memory=1g",
            "--network=none",      
            "--read-only",          
            "-p", f"{deployment.port}:8000",
            "--security-opt=no-new-privileges",
            image_name
        ]

        container_id = subprocess.check_output(run_cmd).decode().strip()
        deploy.docker_container_id = container_id
        deploy.endpoint_url = f"http://YOUR_SERVER_IP:{deployment.port}/predict"
        deploy.status = "active"
        deploy.save()

        return {"status": "success"}
    except Exception as e:
        deploy.status = "failed"
        deploy.logs = str(e)
        self.retry(exc=e, countdown=5)




          

