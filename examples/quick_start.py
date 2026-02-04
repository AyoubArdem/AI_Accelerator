# AI Accelerator - Quick Start Example

"""
This example demonstrates how to use AI Accelerator to deploy and monitor a machine learning model.

Prerequisites:
1. Install AI Accelerator: pip install ai-accelerator
2. Have Docker running
3. Have a trained ML model (pickle file)

Steps:
1. Start the platform
2. Create a project and model version
3. Deploy the model
4. Monitor performance
5. Check for drift
"""

import requests
import json
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api"

# Example usage functions
def authenticate_user(username: str, password: str):
    """Authenticate and get JWT token"""
    url = f"{BASE_URL}{API_PREFIX}/auth/login/"
    data = {"username": username, "password": password}

    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()["access"]
    else:
        raise Exception(f"Authentication failed: {response.text}")

def create_project(token: str, project_data: dict):
    """Create a new project"""
    url = f"{BASE_URL}{API_PREFIX}/deployments/projects/"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(url, json=project_data, headers=headers)
    return response.json()

def upload_model_version(token: str, project_id: int, model_path: str):
    """Upload a model version"""
    url = f"{BASE_URL}{API_PREFIX}/deployments/versions/"
    headers = {"Authorization": f"Bearer {token}"}

    with open(model_path, 'rb') as f:
        files = {'model_file': f}
        data = {
            'project': project_id,
            'version': '1.0.0',
            'description': 'Initial model version'
        }
        response = requests.post(url, files=files, data=data, headers=headers)

    return response.json()

def deploy_model(token: str, model_version_id: int, port: int = 8080):
    """Deploy a model version"""
    url = f"{BASE_URL}{API_PREFIX}/deployments/deploy/"
    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "model_version_id": model_version_id,
        "port": port
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()

def check_drift(token: str, deployment_id: int, sample_data: list):
    """Check for data drift"""
    url = f"{BASE_URL}{API_PREFIX}/monitoring/drift/"
    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "deployment_id": deployment_id,
        "samples": sample_data
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()

# Example workflow
def main():
    # Step 1: Authenticate
    print("🔐 Authenticating...")
    token = authenticate_user("your_username", "your_password")
    print("✅ Authentication successful")

    # Step 2: Create project
    print("📁 Creating project...")
    project_data = {
        "name": "fraud_detection_model",
        "description": "Credit card fraud detection model",
        "owner": "your_username"
    }
    project = create_project(token, project_data)
    print(f"✅ Project created: {project['name']}")

    # Step 3: Upload model
    print("📤 Uploading model...")
    model_version = upload_model_version(token, project['id'], "path/to/your/model.pkl")
    print(f"✅ Model uploaded: v{model_version['version']}")

    # Step 4: Deploy model
    print("🚀 Deploying model...")
    deployment = deploy_model(token, model_version['id'], port=8080)
    print(f"✅ Model deployed on port {deployment['port']}")

    # Step 5: Monitor for drift
    print("📊 Checking for drift...")
    sample_data = [
        [0.1, 0.2, 0.3, 0.4, 0.5],  # Example feature vector
        [0.2, 0.3, 0.4, 0.5, 0.6],  # Another sample
    ]
    drift_result = check_drift(token, deployment['id'], sample_data)
    print(f"📈 Drift analysis: {drift_result}")

    print("\n🎉 AI Accelerator workflow completed successfully!")

if __name__ == "__main__":
    main()