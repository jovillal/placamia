# Infrastructure

Infrastructure in this repository is intentionally minimal.

The current foundation includes only a local PostgreSQL Docker Compose file for
developer setup:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

Production deployment, cloud infrastructure, Kubernetes, Terraform, and CI/CD
deployment automation are out of scope for the MVP foundation.
