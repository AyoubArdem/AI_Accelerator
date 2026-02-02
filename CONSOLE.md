# 🚀 AIAC Console Usage Guide

## How to Run and Use the AIAC Console

### Prerequisites

Before using the AIAC CLI, ensure you have:

1. **Django server running** in the background
2. **Virtual environment activated**
3. **AIAC CLI installed** and accessible

### Starting the Server

First, start your Django development server:

```bash
# Activate virtual environment
source env1/Scripts/activate  # On Windows: env1\Scripts\activate

# Start Django server
python manage.py runserver

# Server will be available at: http://127.0.0.1:8000
```

### Using the AIAC Console

Once the server is running, open a **new terminal window** and start using the AIAC CLI:

```bash
# Activate virtual environment in new terminal
source env1/Scripts/activate  # On Windows: env1\Scripts\activate

# Check CLI help
aiac --help

# View available command groups
aiac

# Get help for specific command group
aiac deployment --help
aiac monitoring --help
aiac governance --help
aiac auth --help
```

### Complete Setup and Usage Workflow

```bash
# Terminal 1: Start the server
source env1/Scripts/activate
python manage.py runserver

# Terminal 2: Use the CLI
source env1/Scripts/activate

# 1. Register/Login first
aiac auth register
# or
aiac auth login

# 2. Create and manage projects
aiac deployment create-project-deployment
aiac deployment list-projects

# 3. Add model versions
aiac deployment create-model-version
aiac deployment list-model-versions

# 4. Deploy models
aiac deployment deploy-model-version
aiac deployment list-deployments

# 5. Monitor deployments
aiac monitoring deploy-stats
aiac monitoring detect-drift

# 6. Set up governance
aiac governance create-policy
aiac governance apply-policy
aiac governance view-violations
```

### CLI Configuration

The AIAC CLI automatically connects to your running Django server. Make sure:

- ✅ **Server is running** on the expected port (default: 8000)
- ✅ **Virtual environment** is activated in CLI terminal
- ✅ **Authentication** is completed before accessing protected endpoints
- ✅ **Network connectivity** between CLI and server (if running on different machines)

### Troubleshooting

**Common issues:**

```bash
# If CLI can't connect to server
# Make sure server is running on correct port
python manage.py runserver 8000

# If authentication fails
# Check your login credentials
aiac auth login

# If commands show connection errors
# Verify server is accessible
curl http://127.0.0.1:8000/api/schema/
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

### Available Commands Reference

#### Authentication Commands
```bash
aiac auth register    # Register a new user account
aiac auth login       # Login to get access tokens
aiac auth logout      # Logout and invalidate tokens
```

#### Deployment Commands
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

#### Monitoring Commands
```bash
aiac monitoring deploy-stats                # View deployment statistics
aiac monitoring deploy-records              # View deployment monitoring records
aiac monitoring alert                       # View deployment alerts
aiac monitoring resolve-alert               # Resolve a specific alert
aiac monitoring detect-drift                # Check for data drift on model version
aiac monitoring samples                     # Post samples for drift analysis
```

#### Governance Commands
```bash
aiac governance create-policy               # Create a new governance policy
aiac governance list-policies               # List all governance policies
aiac governance delete-policy               # Delete a governance policy
aiac governance apply-policy                # Apply a policy to a deployment
aiac governance view-violations             # View policy violations
aiac governance metrics                     # View violation metrics
aiac governance alert-logs                  # View alert logs for violations
```