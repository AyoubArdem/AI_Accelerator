
# 🚀 AI Accelerator Platform

**AI Accelerator** is an end-to-end platform designed to **deploy, monitor, and govern machine learning models in production** in a secure, scalable, and auditable way.

The project aims to be a **core MLOps foundation** for companies, ML teams, and developers who want to move from experimental notebooks to **real production-grade AI systems**.

## 📚 Documentation & Resources

| Document | Description |
|----------|-------------|
| [**README.md**](README.md) | Project overview, setup, and usage guide |
| [**CONSOLE.md**](CONSOLE.md) | Detailed AIAC CLI usage instructions |
| [**CONTRIBUTING.md**](CONTRIBUTING.md) | Guidelines for contributing to the project |
| [**CHANGELOG.md**](CHANGELOG.md) | Version history and release notes |
| [**SECURITY.md**](SECURITY.md) | Security policy and vulnerability reporting |
| [**CODE_OF_CONDUCT.md**](CODE_OF_CONDUCT.md) | Community standards and behavior guidelines |
| [**LICENSE**](LICENSE) | MIT License terms |

### 🚀 Quick Start
- **Setup**: See [Requirements & Dependencies](#-requirements--dependencies) section
- **API Docs**: Visit `http://127.0.0.1:8000/api/schema/swagger-ui/` after setup
- **CLI**: See [CONSOLE.md](CONSOLE.md) for command-line usage

---

## 🎯 Project Vision & Goals

## 🎯 Project Vision & Goals

Modern AI teams face critical challenges:

* ❌ Manual and inconsistent model deployment
* ❌ Lack of monitoring after deployment
* ❌ No detection of **data drift / model drift**
* ❌ Missing governance and policy enforcement
* ❌ Poor auditability and traceability
* ❌ Over-reliance on complex UIs instead of DevOps tools

✅ **AI Accelerator** addresses these challenges by providing:

* Automated model deployment
* Continuous monitoring & drift detection
* Governance and policy-based control
* Security-first architecture
* A powerful CLI for engineers

---

## 🧱 High-Level Architecture

```
                ┌─────────────┐
                │     CLI     │  ← aiac
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │   Django     │
                │   Backend    │
                └──────┬──────┘
        ┌──────────────┼────────────────┐
        │              │                │
┌───────▼───────┐ ┌────▼────────┐ ┌─────▼─────────┐
|Deployment App │ │ Monitoring  │ │ Governance    │
│ (Docker + API)│ │ (Drift etc) │ │ (Policies)    │
└───────────────┘ └─────────────┘ └───────────────┘
```

---

## 📦 Core Applications

### 1️⃣ Deployment App

Responsible for **deploying ML models as real services**.

**Key features:**

* Model version management
* Docker-based deployment
* Automatic FastAPI inference service
* Deployment lifecycle tracking (deploying / active / failed)
* Port governance and runtime control

**Why it matters:**

> Turns ML models into scalable, production-ready APIs.

---

### 2️⃣ Monitoring App

Responsible for **observing model behavior in production**.

**Key features:**

* Collects production features and predictions
* Performance monitoring (latency, usage)
* **Data drift & feature drift detection**
* Drift history tracking
* Alerting and audit integration

**Drift metrics supported:**

* Population Stability Index (PSI)
* Kolmogorov–Smirnov test
* Wasserstein distance

**Why it matters:**

> A model without monitoring is a silent failure waiting to happen.

---

### 3️⃣ Governance App

Responsible for **policies, compliance, and control**.

**Key features:**

* Declarative governance policies (YAML / metadata-based)
* Role-based access control (RBAC)
* Policy enforcement across deployment & monitoring
* Violation tracking
* Read-only audit access

**An example of Metadata-based**

# metadata.yaml
* version: 1.0

# =========================
# Role-Based Access Control
# =========================
> role_permissions:
  * admin:
    - deployment:*
    - monitoring:*
    - governance:*
    - audit:read

  * engineer:
    - deployment:read
    - deployment:write
    - monitoring:read

  * auditor:
    - audit:read

# =========================
# Deployment Runtime Config
# =========================
> deployment:
  * id : deployment.id,
  * name : deployment.name,
  * port : deployment.port,
  * status : deployment.status,

# =========================
# Drift Monitoring Config
# =========================
> drift_monitoring:
  * enabled: true

  * check_strategy:
    - type: request_based              # request_based | time_based
    - every_n_requests: 1000           # used if request_based
    - interval_minutes: 60             # used if time_based

> monitoring: 
  * enabled: True

                
            

> metrics:

    * psi:
       - enabled: true
       - warning: 0.1
       - critical: 0.25
    
    * ks_test:
       - enabled: true
       - p_value_threshold: 0.05

    * wasserstein:
      - enabled: true
      - warning: 0.2

  

**Example policies:**

* Block deployment outside allowed port ranges
* Freeze models when severe drift is detected
* Restrict actions based on user roles
* Require manual approval for risky operations

---

### 4️⃣ AIAC – Command Line Interface

**professional CLI** for interacting with the platform.

**Built with:**

* Typer
* Rich

**Capabilities:**

* Deploy and manage models
* Monitor metrics and drift
* Inspect audit logs
* Validate governance policies
* Automate workflows (CI/CD friendly)

**Why CLI?**

* Designed for ML Engineers & DevOps
* Scriptable and automatable
* Faster and more reliable than GUIs

---

## �️ CLI Commands Reference

The AIAC CLI provides comprehensive command-line access to all platform features. Commands are organized into logical groups for easy navigation.

### Authentication Commands

```bash
# Register a new user account
aiac auth register

# Login to get access tokens
aiac auth login

# Logout and invalidate tokens
aiac auth logout
```

### Deployment Commands

```bash
# Project Management
aiac deployment create-project-deployment    # Create a new project
aiac deployment list-projects               # List all projects
aiac deployment delete-project              # Delete a project

# Model Version Management
aiac deployment create-model-version        # Create a new model version
aiac deployment list-model-versions         # List all model versions
aiac deployment delete-model-version        # Delete a model version

# Deployment Operations
aiac deployment deploy-model-version        # Deploy a model version
aiac deployment redeploy-model              # Redeploy an existing deployment
aiac deployment stop-deployment             # Stop a running deployment
aiac deployment delete-deployment           # Delete a deployment
aiac deployment list-deployments            # List all deployments
aiac deployment get-deployment-details      # Get detailed deployment info
```

### Monitoring Commands

```bash
# Deployment Monitoring
aiac monitoring deploy-stats                # View deployment statistics
aiac monitoring deploy-records              # View deployment monitoring records
aiac monitoring alert                       # View deployment alerts

# Alert Management
aiac monitoring resolve-alert               # Resolve a specific alert

# Data Drift Detection
aiac monitoring detect-drift                # Check for data drift on model version
aiac monitoring samples                     # Post samples for drift analysis
```

### Governance Commands

```bash
# Policy Management
aiac governance create-policy               # Create a new governance policy
aiac governance list-policies               # List all governance policies
aiac governance delete-policy               # Delete a governance policy

# Policy Application
aiac governance apply-policy                # Apply a policy to a deployment

# Compliance Monitoring
aiac governance view-violations             # View policy violations
aiac governance metrics                     # View violation metrics
aiac governance alert-logs                  # View alert logs for violations
```

### Command Usage Examples

```bash
# Complete workflow example
aiac auth login                                    # Authenticate first
aiac deployment create-project-deployment          # Create project
aiac deployment create-model-version               # Add model version
aiac deployment deploy-model-version               # Deploy the model
aiac monitoring deploy-stats                       # Monitor performance
aiac governance create-policy                      # Set up governance
aiac governance apply-policy                       # Apply policy to deployment
```

### Interactive Prompts

Most commands use interactive prompts for required parameters:

```bash
aiac deployment create-project-deployment
# Will prompt for: owner, project_name, description

aiac deployment deploy-model-version
# Will prompt for: user_id, model_version_id, port
```

### Output Formatting

Commands use **Rich** library for beautiful terminal output:
- 📊 **Tables** for listing data
- 🎨 **Colored output** for status and warnings
- 📋 **Structured information** display
- ⚠️ **Clear error messages** and success confirmations

---

## �🔐 Security by Design

Security is a **core principle**, not an afterthought:

* JWT-based authentication
* Role-Based Access Control (RBAC)
* Scoped permissions
* API keys for inference
* Service tokens for monitoring agents
* Immutable audit logs
* Clear separation of roles:

  * Admin
  * Engineer
  * Auditor

---

## 🧠 Why This Project Matters

* 🔹 Combines **ML, Backend, DevOps, and Governance**
* 🔹 Inspired by real-world platforms:

  * AWS SageMaker
  * Google Vertex AI
  * MLflow + Kubernetes ecosystems
* 🔹 Suitable for:

  * Advanced learning
  * Research-to-production workflows
  * Startup or enterprise foundations
* 🔹 Fully extensible and modular

---

## 🛠️ Tech Stack

* Python
* Django & Django REST Framework
* FastAPI
* Docker
* Celery & Redis
* PostgreSQL
* Typer & Rich
* YAML-based governance policies

---
## 📦 Requirements & Dependencies

### System Requirements

- **Python**: 3.8 or higher
- **Docker**: For containerized model deployment
- **PostgreSQL**: Primary database (or SQLite for development)
- **Redis**: For Celery task queue and caching

### Core Dependencies

Install the main requirements:

```bash
pip install -r requirements.txt
```

**Main requirements include:**
- `Django` - Web framework
- `djangorestframework` - API framework
- `djangorestframework-simplejwt` - JWT authentication
- `drf-spectacular` - API documentation
- `django-cors-headers` - CORS handling
- `python-decouple` - Environment variable management
- `psycopg2-binary` - PostgreSQL adapter
- `celery` - Asynchronous task queue
- `django-redis` - Redis cache backend
- `PyJWT` - JWT token handling

### AIAC CLI Dependencies

For the command-line interface:

```bash
pip install -r aiac/requirments.txt
```

**CLI requirements include:**
- `typer` - Command-line interface framework
- `rich` - Beautiful terminal output
- `requests` - HTTP client for API calls
- `click` - Command-line utilities

### Model Deployment Dependencies

For model serving and inference:

```bash
pip install -r deployment/requirements.txt
```

**Deployment requirements include:**
- `fastapi` - High-performance API framework
- `uvicorn` - ASGI server
- `numpy`, `scipy`, `pandas` - Data processing
- `scikit-learn`, `joblib` - Machine learning
- `torch`, `tensorflow` - Deep learning frameworks
- `onnxruntime` - Model inference optimization

### Monitoring Dependencies

For system monitoring and drift detection:

```bash
pip install -r monitoring/requirements.txt
```

**Monitoring requirements include:**
- `requests` - API communication
- `psutil` - System resource monitoring
- `docker` - Container management

### Development Setup

1. **Create virtual environment:**
   ```bash
   python -m venv env1
   source env1/Scripts/activate  # On Windows
   # or
   source env1/bin/activate     # On Linux/Mac
   ```

2. **Install all dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r aiac/requirments.txt
   pip install -r deployment/requirements.txt
   pip install -r monitoring/requirements.txt
   ```

3. **Database setup:**
   ```bash
   # For development (SQLite)
   python manage.py migrate

   # For production (PostgreSQL)
   # Configure DATABASE_URL in .env file
   python manage.py migrate
   ```

4. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

### Optional Dependencies

- **Development tools:**
  - `black` - Code formatting
  - `flake8` - Linting
  - `pytest` - Testing framework

- **Documentation:**
  - `sphinx` - Documentation generation

---
## � API Documentation

The platform provides comprehensive API documentation through **Swagger UI**, allowing you to explore and test all available endpoints interactively.

### Accessing Swagger UI

1. **Start the Django development server:**
   ```bash
   python manage.py runserver
   ```

2. **Open your browser and navigate to:**
   ```
   http://127.0.0.1:8000/api/schema/swagger-ui/
   ```

3. **Alternative documentation formats:**
   - **Redoc UI:** `http://127.0.0.1:8000/api/schema/redoc/`
   - **Raw OpenAPI Schema:** `http://127.0.0.1:8000/api/schema/`

### What you'll find in the documentation:

* 🔍 **Interactive API Explorer** - Test endpoints directly from the browser
* 📋 **Complete endpoint listing** - All available API operations
* 📝 **Request/Response schemas** - Detailed data structures
* 🔐 **Authentication requirements** - JWT token usage
* 📊 **Model schemas** - Data models and relationships

### Authentication

To test protected endpoints, you'll need to:

1. Obtain a JWT token from the authentication endpoints
2. Click "Authorize" in Swagger UI
3. Enter your token in the format: `Bearer <your-jwt-token>`

---

## �🚧 Project Status

> 🚀 Actively under development
> Core architecture is stable and production-oriented

---

## 🤝 Call for Contributors

**AI Accelerator is open for collaboration and contributions.**

We welcome:

* Machine Learning Engineers
* Backend Developers
* DevOps Engineers
* Security & Governance enthusiasts

**Future roadmap ideas:**

* Web-based dashboard
* Automated retraining pipelines
* Advanced drift visualization
* Kubernetes & cloud-native support
* Multi-tenant SaaS mode

📌 Feel free to:

* Fork the repository
* Propose features
* Open issues
* Submit pull requests





**AI Accelerator** is more than a project —
it is a **production-grade AI platform blueprint**.

> Our goal is to make AI deployment, monitoring, and governance
> structured, secure, and scalable —
> from experimentation to real-world impact.

🚀 **Let’s build the future of AI infrastructure together.**

