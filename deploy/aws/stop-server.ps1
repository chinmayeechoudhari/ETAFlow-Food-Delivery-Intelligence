<#
.SYNOPSIS
  Stops the ETAFlow server between demos. Compute billing stops; disk and IP cost about $5/month.
#>
param([string]$StackName = "etaflow", [string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

$o = Get-EtaflowStackOutput -StackName $StackName -Region $Region
aws ec2 stop-instances --region $Region --instance-ids $o.InstanceId | Out-Null
Assert-NativeSuccess "Stopping $($o.InstanceId)"
aws ec2 wait instance-stopped --region $Region --instance-ids $o.InstanceId
Assert-NativeSuccess "Waiting for the server to stop"
Write-Host "Server $($o.InstanceId) is stopped. Start it again with .\deploy\aws\start-server.ps1"
