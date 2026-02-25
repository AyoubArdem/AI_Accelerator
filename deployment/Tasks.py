import subprocess
import os
import shutil
import tempfile
import time
from pathlib import Path
from celery import shared_task
from deployment.models import Deployment
from governance.utils import LogAction
import requests

@shared_task(bind=True, max_retries=3, soft_time_limit=300, time_limit=400)
def deploy_model_task(self, deployment_id):
    deploy = None
    try:
        deploy = Deployment.objects.get(id=deployment_id)
        model_path = deploy.model_version.field_file.path

       
        deploy.status = Deployment.StatusChoices.DEPLOYING
        deploy.logs = "Preparing runtime files"
        deploy.save()

        # On redeploy, clean up the previous container to free the port.
        if deploy.docker_container_id:
            try:
                subprocess.run(
                    ["docker", "stop", deploy.docker_container_id],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                subprocess.run(
                    ["docker", "rm", deploy.docker_container_id],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
            except Exception:
                # Ignore cleanup errors; a later docker run/build will surface actionable errors.
                pass

        runtime_folder = tempfile.mkdtemp(prefix=f"deploy_{deployment_id}_")

        runtime_src = Path(__file__).resolve().parent
        required_files = ["requirements.txt", "fast_api.py", "Dockerfile"]
        missing_files = [name for name in required_files if not (runtime_src / name).exists()]
        if missing_files:
            raise FileNotFoundError(
                "Runtime packaging is incomplete. Missing deployment runtime file(s): "
                f"{', '.join(missing_files)}. Reinstall/upgrade `ai-accelerator` package."
            )

        for file_name in required_files:
            shutil.copy(runtime_src / file_name, runtime_folder)

        
        shutil.copy(model_path, f"{runtime_folder}/model.pkl")

        
        image_name = f"model_deploy_{deploy.id}"
        deploy.logs = "Building Docker image"
        deploy.save(update_fields=["logs"])
        subprocess.run(
            ["docker", "build", "-t", image_name, runtime_folder],
            check=True,
            timeout=1200,
        )

     
        run_cmd = [
            "docker", "run", "-d",
            "--cpus=1",
            "--memory=1g",
            "--network=bridge",
            "--read-only",
            "-p", f"{deploy.port}:8000",
            "--security-opt=no-new-privileges",
            image_name
        ]
        deploy.logs = "Starting container"
        deploy.save(update_fields=["logs"])
        run_result = subprocess.run(
            run_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        container_id = run_result.stdout.strip()

        
        deploy.docker_container_id = container_id
        deploy.endpoint_url = f"http://127.0.0.1:{deploy.port}/predict"
        deploy.logs = "Waiting for runtime health check"
        deploy.save(update_fields=["docker_container_id", "endpoint_url", "logs"])

        health_url = f"http://127.0.0.1:{deploy.port}/health"
        healthy = False
        for _ in range(20):
            try:
                health_resp = requests.get(health_url, timeout=2)
                if health_resp.status_code == 200:
                    healthy = True
                    break
            except requests.RequestException:
                pass
            time.sleep(1)

        if not healthy:
            try:
                container_logs = subprocess.check_output(
                    ["docker", "logs", container_id], stderr=subprocess.STDOUT, timeout=10
                ).decode(errors="ignore")
            except Exception:
                container_logs = "Container health check failed and logs could not be retrieved."
            deploy.status = Deployment.StatusChoices.FAILED
            deploy.logs = f"Container did not become healthy. {container_logs[:1200]}"
            deploy.save(update_fields=["status", "logs"])
            return {"status": "failed", "error": "Container health check failed"}

        deploy.status = Deployment.StatusChoices.ACTIVE
        deploy.logs = "Deployment active"
        deploy.save(update_fields=["status", "logs"])
        try:
            mv = deploy.model_version
            mv.deployed = True
            mv.save(update_fields=["deployed"])
        except Exception:
            # Do not fail deployment if model-version flag update fails.
            pass

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
                "name": f"deployment-{deploy.id}",
                "port": deploy.port,
                "status": deploy.status
               }
            ],
            "monitoring": {
                "enabled": True,
                
            }
        }
        try:
            LogAction(
                user=deploy.user,
                action="DEPLOY",
                description=f"Deployment started for model version {deploy.model_version.id} ({deploy.model_version.projet.name})",
                metadata=meta_data,
                deployment=deploy,
                severity="medium",
            )
        except Exception as audit_err:
            deploy.logs = f"Deployment active. Governance audit logging failed: {audit_err}"
            deploy.save(update_fields=["logs"])

        try:
            from monitoring.Tasks import CollectAndStoreMetrics
            CollectAndStoreMetrics.apply(args=[deployment_id])
        except Exception as monitor_sync_err:
            deploy.logs = f"Deployment active. Initial monitoring collection failed: {monitor_sync_err}"
            deploy.save(update_fields=["logs"])

        try:
            from monitoring.Tasks import start_monitor_agent
            start_monitor_agent.delay(deployment_id)
        except Exception as monitor_err:
            try:
                from monitoring.Tasks import CollectAndStoreMetrics
                CollectAndStoreMetrics.apply(args=[deployment_id])
            except Exception:
                deploy.logs = f"Deployment active. Monitoring agent start failed: {monitor_err}"
                deploy.save(update_fields=["logs"])
        return {"status": "success"}

    except subprocess.TimeoutExpired as e:
        if deploy is not None:
            deploy.status = Deployment.StatusChoices.FAILED
            deploy.logs = f"Timeout during deployment step: {e}"
            deploy.save(update_fields=["status", "logs"])
        return {"status": "failed", "error": str(e)}
    except subprocess.CalledProcessError as e:
        stderr = ""
        stdout = ""
        if hasattr(e, "stderr") and e.stderr:
            stderr = str(e.stderr)
        if hasattr(e, "stdout") and e.stdout:
            stdout = str(e.stdout)
        detail = stderr.strip() or stdout.strip() or str(e)
        if deploy is not None:
            deploy.status = Deployment.StatusChoices.FAILED
            deploy.logs = detail[:1200]
            deploy.save(update_fields=["status", "logs"])
        return {"status": "failed", "error": detail}
    except Exception as e:
        detail = str(e)
        if deploy is not None:
            deploy.status = Deployment.StatusChoices.FAILED
            deploy.logs = detail[:1200]
            deploy.save(update_fields=["status", "logs"])
        # Do not raise retry errors to API callers when running in fallback mode.
        return {"status": "failed", "error": detail}
