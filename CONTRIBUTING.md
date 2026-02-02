# 🤝 Contributing to AI Accelerator

Thank you for your interest in contributing to **AI Accelerator**! We welcome contributions from the community to help make this platform even better. This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Reporting Issues](#reporting-issues)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## 🤝 Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors. By participating, you agree to:

- Be respectful and inclusive
- Focus on constructive feedback
- Accept responsibility for mistakes
- Show empathy towards other contributors
- Help create a positive community

## 🚀 Getting Started

### Prerequisites

Before you begin, ensure you have:

- Python 3.8 or higher
- Git
- Docker (for deployment features)
- PostgreSQL or SQLite (for database)
- Redis (for Celery and caching)

### Quick Setup

1. **Fork the repository** on GitHub
2. **Clone your fork:**
   ```bash
   git clone https://github.com/your-username/ai-accelerator.git
   cd ai-accelerator
   ```

3. **Set up development environment:**
   ```bash
   # Create virtual environment
   python -m venv env1
   source env1/Scripts/activate  # Windows
   # or
   source env1/bin/activate     # Linux/Mac

   # Install dependencies
   pip install -r requirements.txt
   pip install -r aiac/requirments.txt
   pip install -r deployment/requirements.txt
   pip install -r monitoring/requirements.txt

   # Install development dependencies
   pip install black flake8 pytest pytest-django pytest-cov
   ```

4. **Set up the database:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

6. **Verify installation:**
   - Visit `http://127.0.0.1:8000/api/schema/swagger-ui/` for API docs
   - Check that the server starts without errors

## 🛠️ Development Setup

### Environment Configuration

Create a `.env` file in the project root:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3  # or PostgreSQL URL
REDIS_URL=redis://localhost:6379
ALLOWED_HOSTS=localhost,127.0.0.1
```

### IDE Setup

We recommend using VS Code with these extensions:
- Python
- Pylance
- Django
- Docker
- GitLens

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
pip install pre-commit
pre-commit install
```

## 💡 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- 🐛 **Bug fixes** - Fix existing issues
- ✨ **Features** - Add new functionality
- 📚 **Documentation** - Improve docs, tutorials, guides
- 🧪 **Tests** - Add or improve test coverage
- 🎨 **UI/UX** - Improve user interface and experience
- 🔧 **Tools** - Development tools, scripts, automation

### Finding Issues to Work On

1. Check the [Issues](https://github.com/your-repo/ai-accelerator/issues) page
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to indicate you're working on it
4. Wait for maintainer approval before starting

### Areas Needing Help

- **Machine Learning Integration**: Model serving, drift detection algorithms
- **Frontend Development**: Web dashboard, admin interface
- **DevOps**: Docker, Kubernetes, CI/CD pipelines
- **Documentation**: Tutorials, API guides, deployment docs
- **Testing**: Unit tests, integration tests, end-to-end tests

## 🔄 Development Workflow

### 1. Choose an Issue

- Select an issue from the GitHub Issues page
- Comment that you're working on it
- Wait for maintainer assignment

### 2. Create a Branch

```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 3. Make Changes

- Write clean, well-documented code
- Follow the coding standards below
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Run tests
pytest

# Run specific test file
pytest aiac/tests/test_something.py

# Run with coverage
pytest --cov=.

# Run Django tests
python manage.py test
```

### 5. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "feat: add new feature description

- What was changed
- Why it was changed
- Any breaking changes
"

# Push to your fork
git push origin feature/your-feature-name
```

### 6. Create a Pull Request

- Go to the original repository on GitHub
- Click "New Pull Request"
- Select your branch
- Fill out the PR template
- Wait for review

## 📝 Coding Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 88 characters (Black default)
- **Imports**: Use absolute imports
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Add type hints where possible

### Code Formatting

We use Black for automatic code formatting:

```bash
# Format code
black .

# Check formatting
black --check .
```

### Linting

Use flake8 for linting:

```bash
# Run linter
flake8 .

# With specific config
flake8 --max-line-length=88 --extend-ignore=E203,W503
```

### Naming Conventions

- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Variables**: `snake_case`
- **Files**: `snake_case.py`

### Django-Specific Guidelines

- **Models**: Use descriptive field names
- **Views**: Use class-based views when possible
- **URLs**: Use descriptive names for URL patterns
- **Templates**: Follow Django template best practices
- **Migrations**: Create meaningful migration files

## 🧪 Testing

### Test Structure

```
tests/
├── __init__.py
├── test_models.py
├── test_views.py
├── test_serializers.py
├── test_cli.py
├── integration/
│   ├── test_deployment_flow.py
│   └── test_monitoring_flow.py
└── fixtures/
    ├── sample_data.json
    └── test_models.json
```

### Writing Tests

```python
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

class TestProjectModel(TestCase):
    def setUp(self):
        # Setup test data
        pass

    def test_project_creation(self):
        # Test project creation
        pass

    def test_project_str_method(self):
        # Test string representation
        pass

class TestProjectAPI(APITestCase):
    def setUp(self):
        # Setup API test data
        pass

    def test_list_projects(self):
        # Test API endpoints
        pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test class
pytest tests/test_models.py::TestProjectModel

# Run with coverage
pytest --cov=. --cov-report=html

# Run Django tests
python manage.py test
```

### Test Coverage Goals

- **Models**: 90%+ coverage
- **Views**: 85%+ coverage
- **Serializers**: 90%+ coverage
- **CLI**: 80%+ coverage
- **Overall**: 85%+ coverage

## 📚 Documentation

### Documentation Types

- **README.md**: Project overview and setup
- **CONSOLE.md**: CLI usage guide
- **API Documentation**: Auto-generated via DRF Spectacular
- **Code Documentation**: Docstrings and comments
- **Architecture Docs**: System design and decisions

### Writing Documentation

- Use clear, concise language
- Include code examples where helpful
- Keep screenshots up to date
- Document breaking changes
- Update docs with new features

### API Documentation

API docs are automatically generated. To update:

```bash
# Generate OpenAPI schema
python manage.py spectacular --file schema.yml

# View in browser
python manage.py runserver
# Visit: http://127.0.0.1:8000/api/schema/swagger-ui/
```

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:

- **Clear title** describing the issue
- **Steps to reproduce** the problem
- **Expected behavior** vs actual behavior
- **Environment details** (OS, Python version, etc.)
- **Error messages** and stack traces
- **Screenshots** if applicable

### Feature Requests

For new features, please provide:

- **Clear description** of the proposed feature
- **Use case** and why it's needed
- **Implementation ideas** if you have them
- **Mockups** or examples if applicable

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or improvement
- `documentation`: Documentation issues
- `good first issue`: Suitable for newcomers
- `help wanted`: Community contribution needed
- `question`: General questions

## 🔄 Pull Request Process

### PR Requirements

Before submitting a PR:

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts

### PR Template

Please fill out the PR template with:

- **Description**: What changes were made and why
- **Type of change**: Bug fix, feature, documentation, etc.
- **Breaking changes**: Any breaking changes?
- **Testing**: How was this tested?
- **Checklist**: All requirements met?

### Review Process

1. **Automated checks** run (tests, linting, formatting)
2. **Maintainer review** for code quality and design
3. **Community feedback** if needed
4. **Approval and merge** or requested changes

### Commit Message Guidelines

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Testing
- `chore`: Maintenance

## 🌐 Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General discussions and questions
- **Pull Request comments**: Code review discussions

### Getting Help

- Check existing issues and documentation first
- Use clear, descriptive titles for issues
- Provide context and examples
- Be patient and respectful

### Recognition

Contributors are recognized through:
- GitHub contributor statistics
- Mention in release notes
- Attribution in documentation
- Community acknowledgments

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

## 🙏 Thank You

Your contributions help make AI Accelerator better for everyone. We appreciate your time and effort in helping build this platform!

---

*This contributing guide is inspired by open source best practices and the Django project's contribution guidelines.*