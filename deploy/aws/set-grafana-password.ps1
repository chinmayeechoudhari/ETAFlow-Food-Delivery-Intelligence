<#
.SYNOPSIS
  Stores the Grafana admin password in AWS SSM Parameter Store (encrypted SecureString).
.DESCRIPTION
  Run this yourself; the password is typed hidden and never written to disk, git or GitHub.
  The server reads it on every deploy. Grafana only applies it the first time it starts;
  to change it later, also change it in Grafana (Profile > Change password).
#>
param([string]$Region = "ap-south-1")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\EtaflowStack.ps1"

function ConvertTo-PlainText {
    param([System.Security.SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

$first = ConvertTo-PlainText (Read-Host -AsSecureString "New Grafana admin password (at least 12 characters)")
$second = ConvertTo-PlainText (Read-Host -AsSecureString "Type it again")
if ($first -ne $second) { throw "The two passwords do not match. Nothing was saved." }
if ($first.Length -lt 12) { throw "Use at least 12 characters. Nothing was saved." }
if ($first -match '[\s''"$`\\]') { throw "Avoid spaces, quotes, `$, backticks and backslashes. Nothing was saved." }

aws ssm put-parameter --region $Region --name "/etaflow/grafana-admin-password" --type SecureString --overwrite --value $first | Out-Null
Assert-NativeSuccess "Saving the password to SSM Parameter Store"
$first = $null; $second = $null
Write-Host "Saved /etaflow/grafana-admin-password in $Region. Grafana login: admin / <your password>."
