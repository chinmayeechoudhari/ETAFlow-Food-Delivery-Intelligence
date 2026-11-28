# ETAFlow Deployment Guide (AWS EC2 + Docker Compose)

**Owner:** Member 3 (Deployment)

This guide takes ETAFlow from your PC to a live public website on AWS:
- the dashboard and API at `http://<server>/`
- interactive API docs at `http://<server>/docs`
- live Grafana monitoring at `http://<server>:3000`

Every AWS resource comes from one CloudFormation template, so one command creates it all and one command deletes it all.

---

## 1. Architecture

```text
 git push to main
       │
       ▼
 GitHub Actions: "ETAFlow CI/CD Pipeline"      (Member 2: lint + full test suite)
       │ success
       ▼
 GitHub Actions: "ETAFlow Deploy (AWS EC2)"   (Member 3)
       │  1. gets short-lived AWS credentials through OIDC (no stored AWS keys)
       │  2. docker build + push ─────────────► Amazon ECR   (repository: etaflow-app)
       │  3. upload compose bundle ───────────► Amazon S3    (deploy bundles, kept 30 days)
       │  4. SSM Run Command ─────────────────► EC2 server   (t3.micro, Mumbai, fixed Elastic IP)
       │                                          /opt/etaflow → docker compose:
       │                                            ├─ etaflow     :80    dashboard + API + /docs
       │                                            ├─ prometheus  (internal) scrapes /metrics/prometheus every 10 s
       │                                            └─ grafana     :3000  "ETAFlow MLOps Production Dashboard"
       ▼
 5. smoke test: GET http://<server>/health must return 200
```

**Main design choices** (full reasoning in `docs/superpowers/specs/2026-11-23-member3-deployment-design.md`):

| Choice | Why |
|---|---|
| One EC2 server running Docker Compose | Cheapest option, and app, Prometheus and Grafana are all live in one place. AWS App Runner (the original plan) closed to new customers on 30 April 2026. |
| FastAPI serves API **and** dashboard on one port | A cloud server exposes one address; the dashboard calls the API on the same origin. |
| CloudFormation (`deploy/aws/etaflow-stack.yaml`) | Infrastructure as code: repeatable, reviewable, and deletable in one step. |
| GitHub OIDC role instead of access keys | No AWS secret keys are stored in GitHub or shared with teammates. |
| No SSH port; SSM Session Manager instead | Smaller attack surface, and no key files to lose. |
| Grafana password in SSM Parameter Store (encrypted) | Never stored in git, GitHub or on a PC; the server refuses to deploy without it. |
| Pinned versions (`deploy/constraints.txt`) | The container loads the saved models with the same scikit-learn 1.9.1 they were trained with. |

---

## 2. Costs (Mumbai `ap-south-1`, approximate, before free tier or credits)

| Item | Server running | Server stopped |
|---|---|---|
| EC2 t3.micro | ~$8 / month | $0 |
| Public IPv4 (Elastic IP) | ~$3.6 / month | ~$3.6 / month |
| 20 GB gp3 disk | ~$1.8 / month | ~$1.8 / month |
| ECR + S3 storage | < $0.50 / month | < $0.50 / month |
| **Total** | **~$14 / month** | **~$6 / month** |

Stop the server between demos (section 8) and delete everything after the project (section 9). Deleting brings the cost to $0.

---

## 3. One-time AWS setup (you do this in the AWS console)

Root is the account owner. Use it **only** for steps 1–2, then use the IAM user.

1. **Protect root.** Sign in as root, open *Account name (top right) → Security credentials*, and choose **Assign MFA device**. Never create access keys for root.
2. **Create the IAM user `etaflow-admin`.**
   1. Go to *IAM → Users → Create user*, name it `etaflow-admin`, and tick **Provide user access to the AWS Management Console**. Choose **I want to create an IAM user** and set a password.
   2. On the permissions page, choose **Attach policies directly** and pick **AdministratorAccess**. (The stack creates IAM roles, so it needs broad rights; this user replaces root for all project work.)
   3. Create the user, then sign out of root.
3. **Sign in as `etaflow-admin`** using the account sign-in URL shown on the user's page, and assign it an **MFA device** too.
4. **Create a CLI access key.** Go to *IAM → Users → etaflow-admin → Security credentials → Create access key* and choose **Command Line Interface (CLI)**. Keep the window open for the next step. Never paste these keys into chat, git or documents.
5. **Configure the AWS CLI on your PC** (PowerShell) and enter the two keys, region `ap-south-1` and output `json`:
   ```powershell
   aws configure
   ```
6. **Check it worked.** The output must end with `user/etaflow-admin`:
   ```powershell
   aws sts get-caller-identity
   ```

---

## 4. Create the AWS resources

From the project folder, in PowerShell:

```powershell
.\deploy\aws\create-stack.ps1
```

This takes 3–5 minutes. It creates:
- the ECR repository;
- the S3 bundle bucket;
- the security group (ports 80 and 3000 only);
- the server role;
- the EC2 server with Docker, Compose and 2 GB swap;
- the Elastic IP;
- the GitHub OIDC provider and the deploy role.

It then prints the URLs and the six GitHub variables you'll need in section 7.

It's safe to run again later, for example to change the server size. The server image (AMI) is fixed on the first run and reused, so a re-run updates the existing server instead of replacing it.

Options:
- Use `-InstanceType t3.small` for a 2 GB server.
- Use `-CreateGitHubOidcProvider false` if your account already has the GitHub OIDC provider.

---

## 5. Set the Grafana admin password

```powershell
.\deploy\aws\set-grafana-password.ps1
```

You type it hidden, twice. It must have at least 12 characters, with no spaces, quotes, `$`, backticks or backslashes. It's stored encrypted as `/etaflow/grafana-admin-password` in SSM Parameter Store. Visitors can **view** Grafana without logging in; only `admin` with this password can edit it.

---

## 6. First deploy (from your PC)

Start Docker Desktop, then run:

```powershell
.\deploy\aws\deploy-now.ps1
```

It builds the image, pushes it to ECR, uploads the bundle, runs `deploy/remote-deploy.sh` on the server through SSM, and waits for `/health`. At the end it prints:

- **Dashboard:** `http://<elastic-ip>/`
- **API docs:** `http://<elastic-ip>/docs`
- **Grafana:** `http://<elastic-ip>:3000/` (send a few predictions from the dashboard and the panels fill in)

You can run `deploy-now.ps1` again at any time to redeploy your current code.

---

## 7. Automatic deploys from GitHub

`.github/workflows/deploy.yml` runs after the CI workflow succeeds on `main`. Until the variables below exist, it is **skipped**, not failed, so nobody's pushes turn red.

A repository admin opens *GitHub repo → Settings → Secrets and variables → Actions → **Variables** tab → New repository variable* and adds the six values that `create-stack.ps1` printed. None of them are secret:

| Variable | Example |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/etaflow-github-deploy` |
| `AWS_REGION` | `ap-south-1` |
| `EC2_INSTANCE_ID` | `i-0abc123...` |
| `ECR_REPOSITORY_URI` | `123456789012.dkr.ecr.ap-south-1.amazonaws.com/etaflow-app` |
| `BUNDLE_BUCKET` | `etaflow-bundlebucket-...` |
| `APP_URL` | `http://13.x.x.x` |

After that, every push to `main` that passes CI is deployed automatically. You can also start it by hand from *Actions → ETAFlow Deploy (AWS EC2) → Run workflow*.

Only **pushes to `main` of this repository** are deployed. CI also runs for pull requests, including pull requests from forks, but a pull request's CI result never triggers a deploy, so unreviewed code can't reach the server. The AWS deploy role also trusts only the repository `chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence`, branch `main`. To deploy from a different repository or branch, re-run `create-stack.ps1 -GitHubRepo owner/name -GitHubBranch branch` and update the `if:` condition in `.github/workflows/deploy.yml`.

---

## 8. Stop and start between demos

```powershell
.\deploy\aws\stop-server.ps1
```
```powershell
.\deploy\aws\start-server.ps1
```

The address stays the same (Elastic IP), and the containers restart by themselves about a minute after the server starts.

---

## 9. Delete everything

```powershell
.\deploy\aws\delete-stack.ps1
```

You type the stack name to confirm. This **permanently** deletes:
- the server and its IP;
- all images and bundles;
- the roles;
- the Grafana password parameter.

ETAFlow then costs $0. Your IAM user `etaflow-admin` stays; delete it in the console if you no longer need it.

---

## 10. Running the same stack locally

```powershell
docker compose up -d --build
```

- **Dashboard:** `http://127.0.0.1:8000/`
- **API docs:** `http://127.0.0.1:8000/docs`
- **Prometheus:** `http://127.0.0.1:9090/`
- **Grafana:** `http://127.0.0.1:3000/` (login `admin` / `admin` locally, or the value of `GRAFANA_ADMIN_PASSWORD` in `.env`)

Stop it with:

```powershell
docker compose down
```

---

## 11. Troubleshooting

| Symptom | What to do |
|---|---|
| `deploy-now.ps1` says the SSM parameter is missing | Run `set-grafana-password.ps1` first. The server refuses to start Grafana without a password. |
| "server setup failed" or "Docker Compose is not available" | The server's first-boot setup failed. Open a Session Manager shell (next row) and read `/var/log/cloud-init-output.log`. Deleting and re-creating the stack starts fresh. |
| Deploy command status `Failed` | The script prints the server's output. To look around on the server: *EC2 → Instances → etaflow-server → Connect → Session Manager*, then `cd /opt/etaflow && docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` and `... logs etaflow`. |
| Page doesn't load on port 80 or 3000 | Wait about a minute after a start or deploy. Check that the server is *running* in the EC2 console. Check that you're using `http://`, not `https://`. |
| Grafana panels empty | Make a few predictions on the dashboard first. Prometheus scrapes every 10 seconds and the panels use 1–5 minute windows. |
| `/health` says `unhealthy` | The model files didn't load. Check `docker compose ... logs etaflow` on the server for the load error. |
| Server slow or containers restarting (out of memory) | Re-run `create-stack.ps1 -InstanceType t3.small`, then `deploy-now.ps1`. |
| GitHub deploy job "skipped" | The repository variables aren't set yet (section 7), or CI didn't pass. |
| GitHub deploy fails at "Configure AWS credentials" | The workflow isn't running from `main` of the trusted repository, or `AWS_DEPLOY_ROLE_ARN` is wrong. |

---

## 12. Explaining it in the viva

**How does a code change reach the live site?**
1. The push to `main` runs CI (lint and tests).
2. When CI passes, the deploy workflow gets temporary AWS credentials through OIDC and builds the Docker image.
3. It pushes the image to ECR and uploads the compose bundle to S3.
4. It uses SSM to tell the EC2 server to pull the image and restart with `docker compose`.
5. Finally, it smoke-tests `/health`.

**Why EC2 + Docker Compose, not App Runner or Kubernetes?**
App Runner closed to new AWS customers in April 2026. Kubernetes is far more than one model service needs. One small server runs the app, Prometheus and Grafana for about $14 a month, and the same compose file runs on a laptop.

**How is it secured?**
- No AWS keys are stored in GitHub; it uses OIDC with a role limited to one repo, one branch and exactly the deploy actions.
- There's no SSH port; admin access goes through SSM.
- The Grafana password lives in encrypted Parameter Store.
- The container runs as a non-root user, and the disk is encrypted.

**How do you monitor the model in production?**
- Prometheus scrapes `/metrics/prometheus`: request counts by status, inference latency histogram, last predicted ETA, and the data-drift flag from the latest drift report.
- Grafana shows throughput, p95 latency, error rate, predicted ETA and drift alert state.

**How do you know the deployed model is the same as the tested one?**
- The image installs exact versions from `deploy/constraints.txt`.
- The same `/predict` example returns 20.29 minutes on a PC and in the container.
