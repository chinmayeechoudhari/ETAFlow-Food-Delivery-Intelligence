# AWS CI/CD & Cloud Deployment

This guide has been replaced by **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**.

## What changed and why

- **AWS App Runner is no longer the target.** App Runner closed to new AWS customers on 30 April 2026. ETAFlow now runs on **one EC2 server with Docker Compose** (app + Prometheus + Grafana), created from `deploy/aws/etaflow-stack.yaml`.
- **The deploy job moved out of `ci.yml`.** It now lives in its own workflow, `.github/workflows/deploy.yml`, which runs after CI passes on `main`.
- **No AWS access keys in GitHub.** The deploy workflow gets short-lived credentials through **GitHub OIDC** from the IAM role `etaflow-github-deploy`, created by the same CloudFormation stack.
- **`buildspec.yml` (AWS CodeBuild) is not used** by the current pipeline.

For setup, deploying, costs, stopping or starting the server, teardown and troubleshooting, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).
