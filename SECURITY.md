# Security

## Model

* **Synthetic data only.** The repository contains no real patient data. Do not upload identifiable health
  information to a public deployment.
* **No persistence.** Uploaded files are processed in memory and never written to the server's disk. Download
  packages are built in a temporary directory that is deleted immediately.
* **Input limits.** Uploads are capped at 200 MB; all values are parsed as text, and parser failures are reported,
  not executed.
* **Container hardening.** Non-root user, slim base image, no build tools at runtime, compatible with a read-only
  root filesystem, health check on `/_stcore/health`. Streamlit's XSRF protection is enabled and usage statistics
  are off.
* **Supply chain.** CI runs `bandit` on the source and `pip-audit` on the runtime dependencies on every push.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Advisories → Report a vulnerability) rather than a
public issue.
