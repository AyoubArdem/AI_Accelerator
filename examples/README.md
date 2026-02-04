# AI Accelerator Examples

This directory contains example scripts and configurations to help you get started with AI Accelerator.

## Quick Start Example

The `quick_start.py` script demonstrates a complete workflow:

1. **Authentication** - Login to get JWT tokens
2. **Project Creation** - Create a new ML project
3. **Model Upload** - Upload your trained model
4. **Deployment** - Deploy model as a REST API
5. **Monitoring** - Check for data drift

### Running the Example

```bash
# Make sure AI Accelerator is running
python manage.py runserver

# Run the example in a new terminal
python examples/quick_start.py
```

### Prerequisites

- AI Accelerator platform running
- A trained ML model (pickle file)
- Docker for model deployment
- Python requests library

## Example Structure

```
examples/
├── quick_start.py          # Complete workflow example
└── README.md              # This file
```

## API Usage Examples

### Authentication

```python
import requests

# Login
response = requests.post("http://localhost:8000/api/auth/login/",
                        json={"username": "user", "password": "pass"})
token = response.json()["access"]

# Use token in headers
headers = {"Authorization": f"Bearer {token}"}
```

### Model Deployment

```python
# Create project
project = requests.post("http://localhost:8000/api/deployments/projects/",
                       json={"name": "my_model", "description": "ML model"},
                       headers=headers)

# Upload model
with open("model.pkl", "rb") as f:
    files = {"model_file": f}
    data = {"project": project.json()["id"], "version": "1.0.0"}
    model_version = requests.post("http://localhost:8000/api/deployments/versions/",
                                 files=files, data=data, headers=headers)

# Deploy
deployment = requests.post("http://localhost:8000/api/deployments/deploy/",
                          json={"model_version_id": model_version.json()["id"], "port": 8080},
                          headers=headers)
```

## CLI Examples

```bash
# Authenticate
aiac auth login

# Create project
aiac deployment create-project-deployment

# Deploy model
aiac deployment deploy-model-version

# Monitor
aiac monitoring deploy-stats
aiac monitoring detect-drift
```

## Contributing Examples

Feel free to contribute additional examples! Common patterns include:

- Different ML frameworks (TensorFlow, PyTorch, scikit-learn)
- Various deployment scenarios
- Custom monitoring setups
- Governance policy examples

Please follow the existing code style and include comprehensive documentation.