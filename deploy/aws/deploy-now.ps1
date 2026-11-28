<#
.SYNOPSIS
  Builds the ETAFlow image on this PC, pushes it to ECR and deploys it to the EC2 server.
.DESCRIPTION
  Same steps as .github/workflows/deploy.yml, for the first deploy or when GitHub isn't set up.
  Needs Docker Desktop running and the AWS CLI configured as etaflow-admin.
.EXAMPLE
  .\deploy\aws\deploy-now.ps1
#>
param(
    [string]$StackName = "etaflow",
    [string]$Region = "ap-south-1",
    [string]$Tag = ("manual-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $repoRoot
try {
    $o = Get-EtaflowStackOutput -StackName $StackName -Region $Region
    $repoUri = $o.EcrRepositoryUri
    $registry = $repoUri.Split("/")[0]
    $image = "${repoUri}:$Tag"

    Write-Host "[1/5] Building $image ..."
    docker build -t $image -t "${repoUri}:latest" .
    Assert-NativeSuccess "docker build"

    Write-Host "[2/5] Pushing to ECR ..."
    # Not a PowerShell pipe: Windows PowerShell re-encodes text piped between programs and can prepend a
    # UTF-8 byte-order mark, which makes ECR reject the login with "400 Bad Request". cmd.exe passes the
    # token through byte for byte.
    cmd /c "aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry"
    Assert-NativeSuccess "ECR login"
    docker push $image
    Assert-NativeSuccess "docker push $image"
    docker push "${repoUri}:latest"
    Assert-NativeSuccess "docker push latest"

    Write-Host "[3/5] Uploading the deploy bundle ..."
    $bundle = Join-Path $env:TEMP "etaflow-bundle-$Tag.tar.gz"
    tar.exe -czf $bundle docker-compose.yml docker-compose.prod.yml monitoring deploy/remote-deploy.sh
    Assert-NativeSuccess "Creating the bundle"
    aws s3 cp $bundle "s3://$($o.BundleBucket)/bundle/$Tag.tar.gz" --region $Region | Out-Null
    Assert-NativeSuccess "Uploading the bundle"
    Remove-Item $bundle -Force

    Write-Host "[4/5] Running the deploy on the server ($($o.InstanceId)) ..."
    $commands = Get-EtaflowRemoteCommand -Bucket $o.BundleBucket -Tag $Tag -Image $image -Region $Region
    $paramFile = Join-Path $env:TEMP "etaflow-ssm-$Tag.json"
    (@{ commands = $commands } | ConvertTo-Json -Compress) | Out-File -FilePath $paramFile -Encoding ascii
    $commandId = aws ssm send-command --region $Region --instance-ids $o.InstanceId `
        --document-name AWS-RunShellScript --comment "ETAFlow deploy $Tag" `
        --parameters "file://$paramFile" --query "Command.CommandId" --output text
    Assert-NativeSuccess "Sending the SSM command"
    Remove-Item $paramFile -Force

    $null = Wait-EtaflowCommand -CommandId $commandId -InstanceId $o.InstanceId -Region $Region
    $result = aws ssm get-command-invocation --region $Region --command-id $commandId --instance-id $o.InstanceId --output json | Out-String | ConvertFrom-Json
    Write-Host $result.StandardOutputContent
    if ($result.Status -ne "Success") {
        Write-Host $result.StandardErrorContent
        throw "Deploy command finished with status '$($result.Status)'."
    }

    Write-Host "[5/5] Waiting for $($o.DashboardUrl)/health ..."
    $deadline = (Get-Date).AddSeconds(120)
    $healthy = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "$($o.DashboardUrl)/health" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch { Start-Sleep -Seconds 5 }
    }
    if (-not $healthy) { throw "The server did not report healthy within 120 seconds." }

    Write-Host ""
    Write-Host "Deployed $image"
    Write-Host "  Dashboard: $($o.DashboardUrl)/"
    Write-Host "  API docs:  $($o.DashboardUrl)/docs"
    Write-Host "  Grafana:   $($o.GrafanaUrl)/"
}
finally {
    Pop-Location
}
