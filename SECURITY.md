# Security Notes

- The application runs as a non-root user inside the container.
- The container build uses a slim Python base image and avoids copying unnecessary files.
- CI enforces unit tests and security scanning via Bandit and Safety.
- Sensitive outputs are not written to logs; audit trails track events without storing raw protected content.
