# Security Policy

Security is a core requirement for AI Accelerator. This project handles model artifacts, deployment runtimes, monitoring data, and governance controls, so responsible vulnerability reporting and secure operation are essential.

## Supported Versions

The following support policy applies for security updates:

| Version | Security Support |
|--------|-------------------|
| Current stable release | Yes |
| Previous minor release | Yes, for 12 months after next release |
| Older releases | No |

If your version is unsupported, upgrade to the latest stable release before requesting a fix.

## Reporting a Vulnerability

If you believe you found a security issue:

1. Do not open a public issue with exploit details.
2. Report via GitHub Discussions: [Security Discussions](https://github.com/AyoubArdem/AI_Accelerator/discussions)
3. Include enough detail for reproduction and impact analysis.

### What to Include

- A clear description of the issue
- Affected component(s) and version(s)
- Step-by-step reproduction
- Proof of concept (minimal and safe)
- Impact assessment (confidentiality, integrity, availability)
- Suggested mitigation (if available)

### Response Targets

- Initial acknowledgment: within 72 hours
- Triage decision: within 7 days
- Status updates: at least every 7 days until resolution

These are targets, not guarantees, but we aim to meet them consistently.

## Coordinated Disclosure

We follow coordinated (responsible) disclosure:

- Please allow time for investigation and patching before public disclosure.
- Avoid sharing exploit details publicly until a fix or mitigation is available.
- We will credit reporters in advisories/releases when permission is granted.

## Security Scope

This policy covers:

- CLI/API authentication and authorization behavior
- Deployment runtime and service exposure
- Monitoring ingestion and drift/alert pipelines
- Governance policy evaluation and enforcement paths
- Dependency and container security risks

Out of scope:

- Best-effort issues without clear security impact
- Vulnerabilities only present in heavily modified forks
- Social engineering attempts without platform weaknesses

## Secure Deployment Guidance

For production usage:

- Use HTTPS and secure reverse proxies.
- Rotate JWT/API/service credentials regularly.
- Restrict network exposure of internal services.
- Apply least-privilege RBAC for users and service accounts.
- Keep Docker base images and Python dependencies updated.
- Enable centralized logs and monitor auth/deployment anomalies.
- Avoid storing secrets in source control or container images.

## Dependency and Patch Management

- Track dependency CVEs and update promptly.
- Prioritize fixes for authentication, remote code execution, and data exposure issues.
- Release notes/changelog should document security-relevant fixes.

## Security Testing Expectations

Recommended controls for maintainers and contributors:

- Dependency vulnerability scanning
- Container image scanning
- Static analysis and linting in CI
- Targeted tests for auth, permissions, and input validation

## Contact

For security reports and related questions:

- Security channel: [Security Discussions](https://github.com/AyoubArdem/AI_Accelerator/discussions)

Use normal GitHub Issues for non-sensitive bugs and feature requests.
