# AWS CI/CD & Cloud Deployment Architecture Guide
**Project:** ETAFlow — Smart Food Delivery Intelligence & Logistics Platform  
**Target Cloud:** Amazon Web Services (AWS)  
**Container Registry:** Amazon ECR (Elastic Container Registry)  
**Compute Targets:** AWS App Runner (Serverless) / Amazon ECS (AWS Fargate) / AWS EC2  

---

## 1. Cloud Architecture Overview

ETAFlow implements an enterprise-grade MLOps continuous integration and continuous deployment (CI/CD) architecture. The platform supports **two flexible deployment pathways**:

```mermaid
flowchart TD
    subgraph Development ["1. Source Control & Gates"]
        Code[Code Commit / Pull Request] --> GH[GitHub Repository]
        GH --> CI[GitHub Actions / CodeBuild]
    end

    subgraph Verification ["2. Automated Quality Gates"]
        CI --> Lint[Ruff Code Linter]
        CI --> Tests[Pytest: 82 Passing Tests]
        CI --> Bench[Latency Benchmark: P95 < 6ms]
        CI --> Audit[Fairness & Responsible AI Audit]
    end

    subgraph AWSCloud ["3. AWS Cloud Infrastructure"]
        Audit -->|Tests Pass| ECR[Amazon ECR Container Registry]
        ECR -->|Automated Sync| AppRunner[AWS App Runner Serverless]
        ECR -.->|Alternative| ECS[Amazon ECS on AWS Fargate]
        AppRunner --> Route53[Public HTTPS URL]
        Route53 --> Users[Operations Dispatch Dashboard]
    end

    style ECR fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    style AppRunner fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    style Tests fill:#10B981,stroke:#059669,stroke-width:2px,color:#fff
    style Audit fill:#10B981,stroke:#059669,stroke-width:2px,color:#fff
```

---

## 2. Pathway A: GitHub Actions $\to$ Amazon ECR $\to$ AWS App Runner (Recommended)

This is the industry-standard approach combining GitHub's developer workflow with AWS's managed container infrastructure.

### How it Works:
1. A developer pushes code or opens a PR on `main`.
2. **GitHub Actions** (`.github/workflows/ci.yml`) runs all 82 test gates, linting, batch inference, latency benchmarks, and fairness audits.
3. Upon approval and merge to `main`, the `deploy-to-aws` job:
   - Authenticates to AWS via `aws-actions/configure-aws-credentials`.
   - Logs into **Amazon ECR** via `aws-actions/amazon-ecr-login`.
   - Builds the optimized production Docker image.
   - Pushes images tagged with both the commit SHA and `:latest` to Amazon ECR.
   - (Optional) Triggers **AWS App Runner** auto-deployment to update the live endpoint with zero downtime.

---

## 3. Pathway B: AWS-Native CI/CD (AWS CodePipeline & CodeBuild)

For evaluations requiring **100% native AWS services**:
- **Source:** AWS CodeCommit or GitHub connection in AWS CodePipeline.
- **Build & Test Engine:** **AWS CodeBuild** executes `buildspec.yml` (located in the project root).
- **Artifacts:** CodeBuild packages the Docker image and publishes it to Amazon ECR.
- **Deploy:** AWS CodeDeploy or App Runner automatically rolls out the new container version.

---

## 4. Step-by-Step Setup Instructions

### Step 1: Create Amazon ECR Repository
Using the AWS Management Console or AWS CLI:

```bash
# Set your AWS region (e.g. ap-south-1 for Mumbai, or us-east-1)
aws configure set default.region ap-south-1

# Create private container repository
aws ecr create-repository \
    --repository-name etaflow-delivery-api \
    --image-scanning-configuration scanOnPush=true \
    --region ap-south-1
```

### Step 2: Configure GitHub Repository Secrets
In your GitHub repository, navigate to **Settings** $\to$ **Secrets and variables** $\to$ **Actions** $\to$ **New repository secret**:

| Secret Name | Value Example | Description |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | `AKIAIOSFODNN7EXAMPLE` | IAM User Access Key |
| `AWS_SECRET_ACCESS_KEY` | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | IAM User Secret Access Key |
| `AWS_REGION` | `ap-south-1` (Mumbai) or `us-east-1` | Target AWS Region |
| `ECR_REPOSITORY` | `etaflow-delivery-api` | Amazon ECR Repository Name |
| `APP_RUNNER_SERVICE_ARN` | *(Optional)* `arn:aws:apprunner:...` | AWS App Runner Service ARN |

> [!NOTE]
> The GitHub Actions pipeline includes an automated credential check. If secrets are not yet configured in GitHub, the CI test gates run successfully and provide clear instructions.

### Step 3: Deploy to AWS App Runner (Serverless Containers)
AWS App Runner is the optimal AWS compute choice for this project because it is fully managed, auto-scaling, and free-tier eligible:

1. Open **AWS App Runner Console** $\to$ Click **Create service**.
2. **Source:** Select **Container registry** $\to$ **Amazon ECR**.
3. **ECR Repository:** Select `etaflow-delivery-api` and tag `latest`.
4. **Deployment trigger:** Choose **Automatic** (App Runner redeploys automatically whenever a new image is pushed to ECR).
5. **Port configuration:** Set port to `8000` (FastAPI backend).
6. **Health check path:** Set to `/health`.
7. Click **Create & Deploy**. In ~3 minutes, AWS provides a live, secure public HTTPS URL (e.g., `https://xyz123.ap-south-1.awsapprunner.com`).

---

## 5. Viva / Presentation Q&A Defense for Sir

When the professor or evaluator asks about AWS CI/CD, use these structured answers:

#### Q1: "How is CI/CD configured on AWS for this project?"
> *"Our project uses a decoupled, production-grade MLOps CI/CD pipeline. On every commit, our CI runner validates code formatting (Ruff), executes 82 comprehensive test gates covering regression accuracy, anti-leakage boundaries, and drift detection, and runs a latency benchmark. Once gates pass on the main branch, our CD pipeline authenticates securely with AWS using IAM credentials, builds our production Docker container, and pushes the immutable image to Amazon Elastic Container Registry (ECR). AWS App Runner or Amazon ECS automatically syncs with the new ECR image and executes a zero-downtime rolling deployment."*

#### Q2: "Why did you choose Amazon ECR over public Docker Hub?"
> *"Amazon ECR provides native AWS IAM role authentication, encrypted artifact storage at rest via AWS KMS, and automated CVE container vulnerability scanning on push. This adheres to enterprise security standards by keeping proprietary ML model weights inside a private cloud perimeter."*

#### Q3: "What is your fallback if GitHub Actions is not used?"
> *"We have bundled a native AWS `buildspec.yml` specification file in the root directory. This allows the entire pipeline to run natively within AWS CodePipeline and AWS CodeBuild without any external third-party CI dependency."*

#### Q4: "How do you ensure zero downtime during model updates?"
> *"AWS App Runner and ECS use rolling green/blue updates. The orchestrator spins up the new container with the updated Random Forest model, polls our `/health` check endpoint until it returns HTTP 200, directs incoming traffic to the new container, and only then tears down the old container."*
