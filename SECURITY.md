# Security

Phinance stores personal financial records. Do not include real account data, `.env`, SQLite databases, API keys, session cookies, or runtime logs in bug reports, screenshots, pull requests, or releases.

If you find a vulnerability, use GitHub's **Report a vulnerability** / private security advisory option for this repository when available. Please avoid posting exploit details or personal data in a public issue. Include the affected version, reproduction steps with sample data, and expected impact.

For a deployment, use HTTPS, a production WSGI server, a private database, a unique Django secret, and login rate limiting at the reverse proxy. The bundled Compose and Windows launchers are development tools. See the README's publishing and deployment section.

If a secret has been published in Git history, revoke or rotate it. Removing a file in a later commit does not remove it from earlier commits or forks.
