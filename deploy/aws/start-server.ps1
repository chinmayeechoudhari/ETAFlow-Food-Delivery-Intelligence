<#
.SYNOPSIS
  Starts the ETAFlow server again. The containers restart automatically; the URL stays the same.
#>
param([string]$StackName = "etaflow", [string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

$o = Get-EtaflowStackOutput -StackName $StackName -Region $Region
aws ec2 start-instances --region $Region --instance-ids $o.InstanceId | Out-Null
Assert-NativeSuccess "Starting $($o.InstanceId)"
aws ec2 wait instance-running --region $Region --instance-ids $o.InstanceId
Assert-NativeSuccess "Waiting for the server to start"
Write-Host "Server is running. Give it about a minute, then open $($o.DashboardUrl)/ and $($o.GrafanaUrl)/"
