<#
.SYNOPSIS
  Permanently deletes every ETAFlow AWS resource: server, IP, images, bundles, roles and the Grafana password.
.DESCRIPTION
  This cannot be undone. Billing for ETAFlow drops to $0. You are asked to type the stack name first.
  Also works on a stack whose creation failed and rolled back (it then has no outputs).
#>
param([string]$StackName = "etaflow", [string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

$o = Get-EtaflowStackOutput -StackName $StackName -Region $Region
Write-Host "This permanently deletes stack '$StackName' in ${Region}:"
if ($o.InstanceId) {
    Write-Host "  server $($o.InstanceId), its IP $($o.DashboardUrl), all images in $($o.EcrRepositoryUri),"
    Write-Host "  all bundles in s3://$($o.BundleBucket), the deploy role, and /etaflow/grafana-admin-password."
} else {
    Write-Host "  (the stack has no outputs - probably a failed or rolled-back create; whatever it holds is removed)"
}
$confirm = Read-Host "Type the stack name ($StackName) to confirm"
if ($confirm -ne $StackName) { Write-Host "Cancelled. Nothing was deleted."; return }

if ($o.BundleBucket) {
    aws s3 rm "s3://$($o.BundleBucket)" --recursive --region $Region | Out-Null
    Assert-NativeSuccess "Emptying the bundle bucket"
}

aws cloudformation delete-stack --stack-name $StackName --region $Region
Assert-NativeSuccess "Requesting stack deletion"
Write-Host "Deleting (this takes a few minutes)..."
aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
Assert-NativeSuccess "Waiting for stack deletion"

# The password parameter may not exist; PowerShell 5.1 would turn the CLI's stderr into an error under "Stop".
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    aws ssm delete-parameter --region $Region --name "/etaflow/grafana-admin-password" 2>$null | Out-Null
} finally {
    $ErrorActionPreference = $previous
}
Write-Host "Stack '$StackName' deleted. ETAFlow no longer costs anything."
