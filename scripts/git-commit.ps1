#Requires -Version 5.0
<#
.SYNOPSIS
  Run prepare_git_commit.py then git commit (pass-through arguments).

.EXAMPLE
  .\scripts\git-commit.ps1 -m "fix: probe timeout"
  .\scripts\git-commit.ps1 --pre-commit-all -m "chore: sync hooks"
#>
param(
    [switch] $PreCommitAll,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $GitCommitArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$prepareArgs = @("scripts/prepare_git_commit.py", "--auto-add-index")
if ($PreCommitAll) {
    $prepareArgs += "--pre-commit-all"
}
& python @prepareArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($null -eq $GitCommitArgs -or $GitCommitArgs.Count -eq 0) {
    Write-Error "Pass git commit arguments, e.g. -m `"your message`""
    exit 2
}

& git commit @GitCommitArgs
exit $LASTEXITCODE
