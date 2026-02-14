
# AI Accelerator Platform

## Project Logo

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.png" />
    <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.png" />
    <img src="assets/logo.png-removebg-preview.png" alt="AI Accelerator Logo" width="220" />
  </picture>
</p>

**AI Accelerator** is an end-to-end platform designed to **deploy, monitor, and govern machine learning models in production** in a secure, scalable, and auditable way.

[![PyPI version](https://img.shields.io/pypi/v/ai-accelerator)](https://pypi.org/project/ai-accelerator/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

The project aims to be a **core MLOps foundation** for companies, ML teams, and developers who want to move from experimental notebooks to **real production-grade AI systems**.

## Project Overview

AI Accelerator is organized as a modular MLOps platform with four core layers:

- Control layer: the `aiac` CLI for operators and CI/CD automation.
- API layer: Django + DRF endpoints for deployment, monitoring, governance, and auth.
- Runtime layer: model-serving runtime (FastAPI-based services created by deployments).
- Background layer: Celery workers for asynchronous tasks (deployment lifecycle, policy/monitoring workflows).

The platform is designed to support the full model lifecycle:

1. Register users and authenticate with JWT.
2. Create projects and model versions.
3. Deploy model versions as live services.
4. Collect runtime records and drift signals.
5. Enforce governance policies and track violations.
6. Review alerts, insights, and audit trails.

## Application Breakdown

### Deployment App (`deployment`)

Primary role: convert model artifacts into running inference services.

What it manages:

- Project and model-version registries.
- Deployment lifecycle states (`PENDING`, `DEPLOYING`, `ACTIVE`, `FAILED`, etc.).
- Runtime endpoint generation (predict, health, docs, UI routes).
- Service-level operations (redeploy, stop, delete, readiness checks).
- Advanced runtime tooling (advisor, services map, traffic shadow analysis).

Operational value:

- Standardizes how models are released.
- Reduces manual deployment mistakes.
- Makes rollout behavior observable and automatable.

### Monitoring App (`monitoring`)

Primary role: continuously observe deployed systems and detect behavior changes.

What it manages:

- Deployment telemetry (CPU, RAM, latency, request/error counters).
- Time-series-like record retrieval and health reporting.
- Drift detection workflows with configurable thresholds/profiles.
- Alert generation and alert resolution workflows.
- Cost intelligence and optimization recommendations.

Operational value:

- Detects issues before they become incidents.
- Helps teams tune reliability and performance.
- Provides data needed for capacity and cost decisions.

### Governance App (`governance`)

Primary role: define and enforce policy controls over deployment and monitoring behavior.

What it manages:

- Policy definitions (including metadata/rules payloads).
- Policy-to-deployment assignment.
- Violation detection and severity tracking.
- Policy engine execution and debug tooling.
- Governance insights and alert logs.

Operational value:

- Adds compliance guardrails to ML operations.
- Improves traceability and accountability.
- Enables policy-driven control instead of ad hoc rules.

### Authentication and User App (`users` / `auth`)

Primary role: identity and access control.

What it manages:

- Account registration and login/logout.
- JWT issuance and token refresh flow.
- Role-based access boundaries for platform actions.

Operational value:

- Secures operational endpoints.
- Supports separation of duties (admin/engineer/auditor patterns).

## How Apps Work Together

- Deployment provides live endpoints and runtime metadata.
- Monitoring consumes runtime activity and produces health/drift/alert signals.
- Governance evaluates those signals plus deployment actions against policy rules.
- Auth ensures every action is attributable to an authenticated identity.

This separation keeps each app focused while enabling integrated platform behavior across the full production AI lifecycle.

## Installation

### From PyPI (Recommended)

```bash
pip install ai-accelerator
```

### From Source

```bash
git clone https://github.com/AyoubArdem/ai-accelerator.git
cd ai-accelerator
pip install -e .
```

### Development Setup

For contributors and development:

```bash
git clone https://github.com/AyoubArdem/ai-accelerator.git
cd ai-accelerator

# Create virtual environment
python -m venv env1
source env1/bin/activate  # On Windows: env1\Scripts\activate

# Install in development mode
pip install -e .
pip install -e ".[dev]"  # Development dependencies

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

## Quick Start

### 1. Start the Platform

```bash
# Start Django development server
python manage.py runserver

# Server will be available at: http://127.0.0.1:8000
```

### 2. Access API Documentation

Visit the interactive API documentation:
- **Swagger UI**: http://127.0.0.1:8000/api/schema/swagger-ui/
- **ReDoc**: http://127.0.0.1:8000/api/schema/redoc/

### 3. Use the CLI

```bash
# Check CLI help
aiac --help
```

## Documentation & Resources

| Document | Description |
|----------|-------------|
| [**README.md**](README.md) | Project overview, setup, and usage guide |
| [**CONSOLE.md**](CONSOLE.md) | Detailed AIAC CLI usage instructions |
| [**CONTRIBUTING.md**](CONTRIBUTING.md) | Guidelines for contributing to the project |
| [**CHANGELOG.md**](CHANGELOG.md) | Version history and release notes |
| [**SECURITY.md**](SECURITY.md) | Security policy and vulnerability reporting |
| [**CODE_OF_CONDUCT.md**](CODE_OF_CONDUCT.md) | Community standards and behavior guidelines |
| [**LICENSE**](LICENSE) | Apache 2.0 License terms |



## Project Vision & Goals

Modern AI teams face critical challenges:

* Manual and inconsistent model deployment
* Lack of monitoring after deployment
* No detection of **data drift / model drift**
* Missing governance and policy enforcement
* Poor auditability and traceability
* Over-reliance on complex UIs instead of DevOps tools

 **AI Accelerator** addresses these challenges by providing:

* Automated model deployment
* Continuous monitoring & drift detection
* Governance and policy-based control
* Security-first architecture
* A powerful CLI for engineers

---

## High-Level Architecture

```
                 +-----------------+
                 |   CLI (`aiac`)  |
                 +--------+--------+
                          |
                 +--------v--------+
                 | Django Backend  |
                 +---+---------+---+
                     |         |
      +--------------+         +----------------+
      |                                       |
+-----v-----------+                 +---------v---------+
| Deployment App  |                 | Monitoring App    |
| (runtime/API)   |                 | (drift/alerts)    |
+-----------------+                 +---------+---------+
                                              |
                                    +---------v---------+
                                    | Governance App    |
                                    | (policies/audit)  |
                                    +-------------------+
```

---

## Core Applications

This section is a quick map. For detailed responsibilities and architecture, see `Application Breakdown` above.

- `deployment`: model versions, runtime services, deployment lifecycle.
- `monitoring`: runtime telemetry, drift detection, alerts, and reporting.
- `governance`: policies, assignments, violations, and enforcement workflows.
- `aiac` CLI: operational interface to automate platform workflows.

### Governance Metadata Example

```yaml
# metadata.yaml
version: 1.0

target: both   # deployment | monitoring | both

role_permissions:
  admin:
    - deployment:*
    - monitoring:*
    - governance:*
    - audit:read
  engineer:
    - deployment:read
    - deployment:write
    - monitoring:read
  auditor:
    - audit:read

deployment:
  id: deployment.id
  name: deployment.name
  port: deployment.port
  status: deployment.status

drift_monitoring:
  enabled: true
  check_strategy:
    type: request_based   # request_based | time_based
    every_n_requests: 1000
    interval_minutes: 60

monitoring:
  enabled: true

metrics:
  psi:
    enabled: true
    warning: 0.1
    critical: 0.25
  ks_test:
    enabled: true
    p_value_threshold: 0.05
  wasserstein:
    enabled: true
    warning: 0.2
```

**Example policies:**

* Block deployment outside allowed port ranges
* Freeze models when severe drift is detected
* Restrict actions based on user roles
* Require manual approval for risky operations

---

## CLI Commands Reference

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
- **Tables** for listing data
- **Colored output** for status and warnings
- **Structured information** display
- **Clear error messages** and success confirmations

---

## API Endpoints

The platform provides REST APIs for all functionality. Key endpoints include:

### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/register/` - User registration
- `POST /api/auth/logout/` - User logout

### Deployment Management
- `GET /api/deployments/projects/` - List projects
- `POST /api/deployments/projects/` - Create project
- `GET /api/deployments/versions/` - List model versions
- `POST /api/deployments/versions/` - Create model version
- `POST /api/deployments/deploy/` - Deploy model
- `GET /api/deployments/` - List deployments

### Monitoring
- `GET /api/monitoring/stats/` - Deployment statistics
- `POST /api/monitoring/drift/` - Check data drift
- `GET /api/monitoring/alerts/` - List alerts

### Governance
- `GET /api/governance/policies/` - List policies
- `POST /api/governance/policies/` - Create policy
- `GET /api/governance/violations/` - List violations

## Authentication & Security

### JWT Token Authentication

The platform uses JWT (JSON Web Tokens) for API authentication:

1. **Login** to get access and refresh tokens
2. **Include token** in Authorization header: `Bearer <access_token>`
3. **Refresh tokens** when they expire using the refresh endpoint

### Role-Based Access Control

Three user roles with different permissions:

- **Admin**: Full access to all features
- **Engineer**: Deployment and monitoring access
- **Auditor**: Read-only access to audit logs and compliance data

### Security Features

- JWT-based authentication
- Role-based permissions
- API key support for model inference
- Service tokens for monitoring agents
- Immutable audit logging
- Input validation and sanitization

---

## Why This Project Matters

* Combines **ML, Backend, DevOps, and Governance**
* Inspired by real-world platforms:

  * AWS SageMaker
  * Google Vertex AI
  * MLflow + Kubernetes ecosystems
* Suitable for:

  * Advanced learning
  * Research-to-production workflows
  * Startup or enterprise foundations
* Fully extensible and modular

---

## Docker Deployment

The platform supports containerized deployment for production environments.

### Quick Start with Docker Compose

```bash
# Clone the repository
git clone https://github.com/AyoubArdem/ai-accelerator.git
cd ai-accelerator

# Start all services
docker-compose up -d

# Services will be available at:
# - Django API: http://localhost:8000
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

### Docker Services

- **web**: Django application server
- **db**: PostgreSQL database
- **redis**: Redis cache and message broker
- **celery**: Asynchronous task worker

### Environment Configuration

Create a `.env` file for configuration:

```env
# Database
DATABASE_URL=postgresql://user:password@db:5432/ai_accelerator

# Redis
REDIS_URL=redis://redis:6379/0

# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# JWT
JWT_SECRET_KEY=your-jwt-secret
```

### Building Custom Images

```bash
# Build the application image
docker build -t ai-accelerator:latest .

# Run with custom configuration
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  ai-accelerator:latest
```
## Requirements & Dependencies

### System Requirements

- **Python**: 3.8 or higher
- **Docker**: For containerized model deployment
- **PostgreSQL**: Primary database (or SQLite for development)
- **Redis**: For Celery task queue and caching

### Core Dependencies

When you install `ai-accelerator`, the following key dependencies are automatically included:

**Main requirements:**
- `Django>=5.2.8` - Web framework
- `djangorestframework>=3.14.0` - API framework
- `djangorestframework-simplejwt>=5.3.0` - JWT authentication
- `drf-spectacular>=0.26.5` - API documentation
- `django-cors-headers>=4.3.1` - CORS handling
- `python-decouple>=3.8` - Environment variable management
- `psycopg2-binary>=2.9.9` - PostgreSQL adapter
- `celery>=5.3.4` - Asynchronous task queue
- `django-redis>=5.4.0` - Redis cache backend
- `redis>=5.0.1` - Redis client
- `PyJWT>=2.8.0` - JWT token handling

**CLI requirements:**
- `typer>=0.9.0` - Command-line interface framework
- `rich>=13.7.0` - Beautiful terminal output
- `docker>=7.0.0` - Container management
- `requests>=2.31.0` - HTTP client

**AI/ML requirements:**
- `numpy>=1.24.3` - Numerical computing
- `scipy>=1.11.4` - Scientific computing
- `tensorflow>=2.15.0` - Deep learning framework

### Development Setup

For contributors and advanced users who want to run from source:

1. **Clone and setup:**
   ```bash
   git clone https://github.com/AyoubArdem/ai-accelerator.git
   cd ai-accelerator
   python -m venv env1
   source env1/bin/activate  # On Windows: env1\Scripts\activate
   ```

2. **Install all dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r deployment/requirements.txt
   pip install -r monitoring/requirements.txt
   pip install -r governance/requirements.txt
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

### Optional Development Dependencies

Install additional development tools:

```bash
pip install -e ".[dev]"
```

This includes:
- `pytest>=7.4.3` - Testing framework
- `pytest-django>=4.5.2` - Django testing utilities
- `black>=23.12.1` - Code formatting
- `flake8>=6.1.0` - Linting
- `isort>=5.13.2` - Import sorting
- `pre-commit>=3.6.0` - Git hooks

---
## API Documentation

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

* **Interactive API Explorer** - Test endpoints directly from the browser
* **Complete endpoint listing** - All available API operations
* **Request/Response schemas** - Detailed data structures
* **Authentication requirements** - JWT token usage
* **Model schemas** - Data models and relationships

### Authentication

To test protected endpoints, you'll need to:

1. Obtain a JWT token from the authentication endpoints
2. Click "Authorize" in Swagger UI
3. Enter your token in the format: `Bearer <your-jwt-token>`

---

## Project Status

**AI Accelerator v0.1.0** is now available on PyPI! 

### Current Status
- **Core functionality** implemented and tested
- **PyPI package** published and installable
- **CLI tool** fully functional
- **API documentation** complete
- **Docker support** for containerized deployment

### Roadmap (Future Releases)

#### v0.2.0 - Enhanced Monitoring
- [ ] Advanced drift visualization
- [ ] Custom monitoring metrics
- [ ] Alert notification system (email/webhooks)
- [ ] Performance benchmarking tools

#### v0.3.0 - Web Dashboard
- [ ] React-based admin interface
- [ ] Real-time monitoring dashboard
- [ ] Model performance analytics
- [ ] Governance policy editor

#### v0.4.0 - Enterprise Features
- [ ] Multi-tenant architecture
- [ ] Advanced RBAC with custom roles
- [ ] Audit log export and compliance reports
- [ ] Integration with cloud platforms (AWS, GCP, Azure)

#### v0.5.0 - Automation & Pipelines
- [ ] Automated model retraining
- [ ] CI/CD pipeline integration
- [ ] A/B testing framework
- [ ] Model versioning with Git integration

### Stability
- **Core APIs**: Stable for production use
- **CLI Interface**: Stable and backward compatible
- **Database Schema**: Stable with migration support
- **Docker Images**: Production-ready

### Support
- **Discussions**: [GitHub Discussions](https://github.com/AyoubArdem/AI_Accelerator/discussions)

---

## Contributing

We welcome contributions from the community! Here's how to get started:

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-username/ai-accelerator.git
cd ai-accelerator

# Create virtual environment
python -m venv env1
source env1/bin/activate  # On Windows: env1\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run database migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Run tests
pytest

# Start development server
python manage.py runserver
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Run all checks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aiac --cov=AI_Accelerator

# Run specific test file
pytest tests/test_deployment.py
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest`
5. Format your code: `black . && isort .`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Areas for Contribution

- **Bug fixes** - Help us squash bugs
- **New features** - Add monitoring metrics, governance policies, etc.
- **Documentation** - Improve docs, add tutorials, examples
- **Testing** - Add more comprehensive tests
- **UI/UX** - Web dashboard, improved CLI output
- **DevOps** - Kubernetes support, CI/CD improvements





## Acknowledgments

AI Accelerator builds upon the excellent work of the open-source community:

- **Django** & **Django REST Framework** - Web framework foundation
- **Typer** & **Rich** - CLI framework and beautiful output
- **Celery** - Asynchronous task processing
- **Docker** - Containerization platform
- **TensorFlow** - Machine learning framework
- **PostgreSQL** & **Redis** - Data storage and caching

Special thanks to all contributors and the MLOps community for inspiration and feedback.

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

```
Copyright 2026 AI Accelerator Team

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## Contact & Support

- **Email**: [ayoub.ardem@example.com]
- **GitHub**: [@AyoubArdem](https://github.com/AyoubArdem)
- **LinkedIn**: [https://www.linkedin.com/in/ayoub-student-08832b2b3]

---

**AI Accelerator** is more than a project; it's a **production-grade AI platform blueprint**.

> Our goal is to make AI deployment, monitoring, and governance structured, secure, and scalable from experimentation to real-world impact.

 **Let's build the future of AI infrastructure together!**





