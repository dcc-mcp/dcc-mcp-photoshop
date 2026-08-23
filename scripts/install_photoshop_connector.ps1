<#
.SYNOPSIS
    Compatibility wrapper for the canonical dcc-mcp-photoshop install lifecycle.

.DESCRIPTION
    This legacy Windows entry point no longer downloads binaries, writes the
    registry, or installs a CCX package. It translates the established switches
    to the cross-platform Install SOP v1 CLI, which owns staged replacement,
    receipts, rollback, readiness verification, and structured exit codes.

.EXAMPLE
    .\install_photoshop_connector.ps1 -Install

.EXAMPLE
    .\install_photoshop_connector.ps1 -Upgrade -WhatIf

.EXAMPLE
    .\install_photoshop_connector.ps1 -Uninstall
#>

[CmdletBinding(DefaultParameterSetName = "Install", SupportsShouldProcess = $true)]
param(
    [Parameter(ParameterSetName = "Install")]
    [switch]$Install,

    [Parameter(ParameterSetName = "Upgrade")]
    [switch]$Upgrade,

    [Parameter(ParameterSetName = "Uninstall")]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = "Rollback")]
    [switch]$Rollback,

    [Parameter(ParameterSetName = "Check")]
    [switch]$CheckVersion,

    [Parameter(ParameterSetName = "Install")]
    [Parameter(ParameterSetName = "Upgrade")]
    [string]$Version,

    [Parameter(ParameterSetName = "Install")]
    [Parameter(ParameterSetName = "Upgrade")]
    [string]$CoreVersion,

    [Parameter(ParameterSetName = "Install")]
    [Parameter(ParameterSetName = "Upgrade")]
    [switch]$NoAutostart,

    [Parameter(ParameterSetName = "Install")]
    [Parameter(ParameterSetName = "Upgrade")]
    [switch]$NoSmoke,

    [Parameter()]
    [switch]$Force,

    [Parameter(ParameterSetName = "Uninstall")]
    [switch]$KeepConfig
)

$ErrorActionPreference = "Stop"

function Invoke-CanonicalLifecycle {
    param([string[]]$Arguments)

    $cli = Get-Command "dcc-mcp-photoshop" -ErrorAction SilentlyContinue
    if ($null -ne $cli) {
        & $cli.Source @Arguments
        return $LASTEXITCODE
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        Write-Error "Install the dcc-mcp-photoshop wheel with Python 3.8+ before using this compatibility wrapper."
        return 10
    }

    & $python.Source -m dcc_mcp_photoshop @Arguments
    return $LASTEXITCODE
}

$verb = "install"
if ($Upgrade) {
    $verb = "upgrade"
}
elseif ($Uninstall) {
    $verb = "uninstall"
}
elseif ($CheckVersion -or $Rollback) {
    $verb = "status"
}

if ($Rollback) {
    Write-Warning "Manual rollback is retired. Failed upgrades roll back atomically; status reports the receipt-backed state."
}
if ($Version -or $CoreVersion -or $NoAutostart -or $NoSmoke -or $Force -or $KeepConfig) {
    Write-Warning "One or more legacy options are accepted for compatibility but are not part of Install SOP v1."
}

$arguments = @($verb, "--json")
$isMutation = $verb -in @("install", "upgrade", "uninstall")
if ($isMutation) {
    if ($PSBoundParameters.ContainsKey("WhatIf")) {
        $arguments += "--dry-run"
    }
    else {
        $arguments += "--yes"
    }
}

$exitCode = Invoke-CanonicalLifecycle -Arguments $arguments
exit $exitCode
