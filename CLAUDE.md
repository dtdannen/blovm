# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

### Docker

```bash
# Build and run the Docker container
docker compose up --build

# Stop the Docker container
docker compose down
```

# File Permission Rules
- NEVER run chmod commands on files intended for Docker containers
- Files in the following locations are Docker-only and should not have permissions changed:
  - `./docker/`
  - `./containers/`
  - Any Dockerfile or docker-compose.yml
  - Files with `.dockerfile` extension
- When working with containerized applications, file permissions are handled by the container runtime
- If permission issues arise, suggest Dockerfile modifications instead of chmod commands

# Docker Workflow
- For permission issues in containers, modify the Dockerfile USER directive
- Use COPY --chown=user:group instead of chmod in containers
- Suggest docker build solutions rather than host filesystem changes

#### Accessing Host Services from Docker

When running services on your host machine (like UI-TARS) that need to be accessed from within the Docker container, use the following configuration in `docker-compose.yml`:

```yaml
services:
  goose-agent:
    # ... other configuration ...
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

This allows the container to access host services using `host.docker.internal` as the hostname.