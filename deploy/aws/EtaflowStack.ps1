# Shared helpers for the ETAFlow AWS scripts. Dot-source it:  . "$PSScriptRoot\EtaflowStack.ps1"
# Works in Windows PowerShell 5.1 and PowerShell 7.

function Assert-NativeSuccess {
    param([string]$What)
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)." }
}

function Get-EtaflowStackOutput {
    param([string]$StackName = "etaflow", [string]$Region = "ap-south-1")
    $json = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs" --output json
    Assert-NativeSuccess "Reading stack '$StackName' outputs"
    $outputs = @{}
    foreach ($item in ($json | Out-String | ConvertFrom-Json)) { $outputs[$item.OutputKey] = $item.OutputValue }
    return $outputs
}

# The server image (AMI) is fixed when the stack is first created. Re-runs reuse it, because a
# changed image id would make CloudFormation replace the server (new empty server, new instance id).
function Resolve-EtaflowAmiId {
    param([string]$StackName = "etaflow", [string]$Region = "ap-south-1")
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"   # PowerShell 5.1 turns native stderr into errors under "Stop"
    try {
        $existing = aws cloudformation describe-stacks --stack-name $StackName --region $Region `
            --query "Stacks[0].Parameters[?ParameterKey=='AmiId'].ParameterValue | [0]" --output text 2>$null
        $found = ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($found -and $existing -and "$existing".Trim() -and "$existing".Trim() -ne "None") {
        return "$existing".Trim()
    }
    $latest = aws ssm get-parameter --region $Region `
        --name "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" `
        --query "Parameter.Value" --output text
    Assert-NativeSuccess "Looking up the latest Amazon Linux 2023 AMI"
    return "$latest".Trim()
}

# Waits for an SSM Run Command to finish and returns its final status. Polls for up to 15 minutes:
# pulling the image on a small server can exceed the AWS CLI waiter's ~100 s limit.
function Wait-EtaflowCommand {
    param([string]$CommandId, [string]$InstanceId, [string]$Region, [int]$TimeoutMinutes = 15, [int]$PollSeconds = 10)
    $status = "Pending"
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $previous = $ErrorActionPreference
    # Right after send-command AWS answers "InvocationDoesNotExist" on stderr; PowerShell 5.1 would
    # turn that into a terminating error under "Stop", so tolerate it and keep polling.
    $ErrorActionPreference = "Continue"
    try {
        while ((Get-Date) -lt $deadline -and @("Pending", "InProgress", "Delayed") -contains $status) {
            Start-Sleep -Seconds $PollSeconds
            $status = aws ssm get-command-invocation --region $Region --command-id $CommandId --instance-id $InstanceId --query "Status" --output text 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $status) { $status = "Pending" }
            Write-Host "  server deploy status: $status"
        }
    } finally {
        $ErrorActionPreference = $previous
    }
    return "$status".Trim()
}

# The shell commands SSM runs on the server for one deploy. .github/workflows/deploy.yml runs the same steps.
function Get-EtaflowRemoteCommand {
    param([string]$Bucket, [string]$Tag, [string]$Image, [string]$Region)
    return @(
        "set -eu",
        "mkdir -p /opt/etaflow",
        "aws s3 cp s3://$Bucket/bundle/$Tag.tar.gz /tmp/etaflow-bundle.tar.gz --region $Region",
        "tar -xzf /tmp/etaflow-bundle.tar.gz -C /opt/etaflow",
        "bash /opt/etaflow/deploy/remote-deploy.sh $Image $Region"
    )
}
