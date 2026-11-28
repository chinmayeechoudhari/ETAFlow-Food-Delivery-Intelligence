<#
.SYNOPSIS
  Creates (or updates) every AWS resource for ETAFlow from deploy/aws/etaflow-stack.yaml.
.DESCRIPTION
  Needs the AWS CLI configured as the etaflow-admin IAM user (run `aws configure` first).
  Prints the stack outputs and the six GitHub repository variables for automatic deploys.
  This creates billable resources (about $14/month while the server runs).
.EXAMPLE
  .\deploy\aws\create-stack.ps1
  .\deploy\aws\create-stack.ps1 -InstanceType t3.small
#>
param(
    [string]$StackName = "etaflow",
    [string]$Region = "ap-south-1",
    [ValidateSet("t3.micro", "t3.small")][string]$InstanceType = "t3.micro",
    [ValidateSet("true", "false")][string]$CreateGitHubOidcProvider = "true",
    [string]$GitHubRepo = "chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence",
    [string]$GitHubBranch = "main"
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

$template = Join-Path $PSScriptRoot "etaflow-stack.yaml"
$amiId = Resolve-EtaflowAmiId -StackName $StackName -Region $Region
Write-Host "Server image (AMI): $amiId"
Write-Host "Creating/updating stack '$StackName' in $Region (this takes 3-5 minutes)..."
aws cloudformation deploy `
    --stack-name $StackName `
    --region $Region `
    --template-file $template `
    --capabilities CAPABILITY_NAMED_IAM `
    --no-fail-on-empty-changeset `
    --parameter-overrides "AmiId=$amiId" "InstanceType=$InstanceType" "CreateGitHubOidcProvider=$CreateGitHubOidcProvider" "GitHubRepo=$GitHubRepo" "GitHubBranch=$GitHubBranch"
Assert-NativeSuccess "CloudFormation deploy"

$o = Get-EtaflowStackOutput -StackName $StackName -Region $Region
Write-Host ""
Write-Host "Stack ready:"
$o.GetEnumerator() | Sort-Object Name | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "GitHub repository variables (Settings > Secrets and variables > Actions > Variables)."
Write-Host "None of these are secret; a repo admin adds them once:"
Write-Host "  AWS_DEPLOY_ROLE_ARN = $($o.DeployRoleArn)"
Write-Host "  AWS_REGION          = $($o.Region)"
Write-Host "  EC2_INSTANCE_ID     = $($o.InstanceId)"
Write-Host "  ECR_REPOSITORY_URI  = $($o.EcrRepositoryUri)"
Write-Host "  BUNDLE_BUCKET       = $($o.BundleBucket)"
Write-Host "  APP_URL             = $($o.DashboardUrl)"
Write-Host ""
Write-Host "Next: .\deploy\aws\set-grafana-password.ps1, then .\deploy\aws\deploy-now.ps1"
