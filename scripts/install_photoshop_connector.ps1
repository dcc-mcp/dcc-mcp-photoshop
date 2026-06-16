<#
.SYNOPSIS
    Install, upgrade, uninstall, or rollback the dcc-mcp Photoshop connector on Windows.

.DESCRIPTION
    All-in-one installer that downloads, configures, smoke-tests, upgrades,
    uninstalls, or rolls back the dcc-mcp Photoshop connector.

    Install mode performs the following steps:
    1. Install/upgrade binaries (dcc-mcp-photoshop + dcc-mcp-server)
       from GitHub Releases to $env:LOCALAPPDATA\dcc-mcp\bin\
    2. Install the UXP .ccx plugin into Photoshop's external plugin dir
    3. Write local registry directory and bridge configuration
    4. Register autostart via HKCU Run key
    5. Optional smoke check: start server, verify gateway health + bridge

    Upgrade mode backs up existing binaries to .rollback, then installs
    the new version while preserving configuration.

    Uninstall mode stops running processes, removes autostart, and
    optionally cleans configuration data.

    Rollback mode restores binaries from the .rollback backup created
    by a previous upgrade.

.PARAMETER Install
    Default action; install the connector (fresh or overwrite).

.PARAMETER Upgrade
    Upgrade the connector: backup existing binaries, install new version,
    preserve configuration.

.PARAMETER Uninstall
    Uninstall the connector: stop processes, remove autostart, clean
    binaries and optional configuration.

.PARAMETER Rollback
    Rollback to the previous version from .rollback backup.

.PARAMETER Version
    Semantic version of dcc-mcp-photoshop to install (e.g. "0.1.18").
    Defaults to the latest release if not specified. Applies to Install
    and Upgrade modes.

.PARAMETER CoreVersion
    Semantic version of dcc-mcp-core (dcc-mcp-server) to install.
    Defaults to the version pinned by the photoshop release's dependency
    constraint, or the latest if unresolved. Applies to Install and
    Upgrade modes.

.PARAMETER NoAutostart
    Skip registering the connector to start automatically with Windows.
    Applies to Install and Upgrade modes.

.PARAMETER NoSmoke
    Skip the post-install smoke check. Applies to Install and Upgrade
    modes.

.PARAMETER KeepConfig
    Preserve configuration and registry data during uninstall.

.PARAMETER CheckVersion
    Compare local installed version against the remote latest release
    without making any changes.

.PARAMETER Force
    Overwrite existing files without prompting.

.PARAMETER WhatIf
    Show what would be done without making any changes.

.EXAMPLE
    .\install_photoshop_connector.ps1 -Install

.EXAMPLE
    .\install_photoshop_connector.ps1 -CheckVersion

.EXAMPLE
    .\install_photoshop_connector.ps1 -Upgrade

.EXAMPLE
    .\install_photoshop_connector.ps1 -Upgrade -Version 0.1.19 -CoreVersion 0.18.35

.EXAMPLE
    .\install_photoshop_connector.ps1 -Uninstall

.EXAMPLE
    .\install_photoshop_connector.ps1 -Uninstall -KeepConfig

.EXAMPLE
    .\install_photoshop_connector.ps1 -Rollback

.EXAMPLE
    .\install_photoshop_connector.ps1 -Version 0.1.18 -CoreVersion 0.18.30

.EXAMPLE
    .\install_photoshop_connector.ps1 -NoAutostart -NoSmoke

.EXAMPLE
    .\install_photoshop_connector.ps1 -WhatIf
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
$InformationPreference = "Continue"

# Capture WhatIf preference for use in helper functions that lack CmdletBinding
$script:WhatIfMode = $PSBoundParameters.ContainsKey('WhatIf') -or [bool]$WhatIf

# ── Constants ────────────────────────────────────────────────────────────────

$PHOTOSHOP_REPO = "dcc-mcp/dcc-mcp-photoshop"
$CORE_REPO = "dcc-mcp/dcc-mcp-core"
$RELEASE_BASE_PS = "https://github.com/$PHOTOSHOP_REPO/releases/download"
$RELEASE_BASE_CORE = "https://github.com/$CORE_REPO/releases/download"

$BIN_DIR = "$env:LOCALAPPDATA\dcc-mcp\bin"
$UXP_DIR = "$env:APPDATA\Adobe\UXP\Plugins\External"
$REGISTRY_DIR = "$env:USERPROFILE\.dcc-mcp\registry"
$CONFIG_DIR = "$env:LOCALAPPDATA\dcc-mcp\config"

$PHOTOSHOP_BINARY = "dcc-mcp-photoshop-windows.exe"
$SERVER_BINARY = "dcc-mcp-server-windows-x86_64.exe"
$PLUGIN_FILE = "dcc-mcp-photoshop-bridge-{0}.ccx"

$GATEWAY_HEALTH_URL = "http://127.0.0.1:9765/health"
$RPC_URL = "http://127.0.0.1:9100/health"

# Autostart script name
$AUTOSTART_SCRIPT_NAME = "start-dcc-mcp-photoshop.cmd"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-WarningMsg {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERR]  $Message" -ForegroundColor Red
}

function Test-WhatIf {
    param([string]$Message)
    if ($script:WhatIfMode) {
        Write-Host "[WHATIF] $Message" -ForegroundColor Magenta
        return $true
    }
    return $false
}

function Get-LatestReleaseVersion {
    param([string]$Repo)
    # Prefer gh CLI (authenticated) over raw API
    $ghExe = Get-Command "gh" -ErrorAction SilentlyContinue
    if ($ghExe) {
        try {
            $tag = & gh release view --repo $Repo --json tagName --jq '.tagName' 2>$null
            if ($tag -match '^v?(.+)$') {
                Write-Info "Resolved $Repo latest version: $($matches[1]) (via gh CLI)"
                return $matches[1]
            }
        }
        catch {
            Write-WarningMsg "gh CLI failed, falling back to REST API"
        }
    }

    $apiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    Write-Info "Fetching latest release version from $apiUrl"
    try {
        $release = Invoke-RestMethod -Uri $apiUrl -Headers @{
            "Accept" = "application/vnd.github+json"
            "User-Agent" = "dcc-mcp-installer/1.0"
        } -UseBasicParsing
        $tag = $release.tag_name
        if ($tag -match '^v?(.+)$') {
            return $matches[1]
        }
        return $tag
    }
    catch {
        Write-WarningMsg "GitHub API rate limited, using fallback version: 0.1.18"
        return "0.1.18"
    }
}

function Get-CoreVersionFromGhRelease {
    param([string]$PhotoshopVersion)
    $ghExe = Get-Command "gh" -ErrorAction SilentlyContinue
    if (-not $ghExe) { return $null }

    try {
        # Download pyproject.toml from the release tag
        & gh release download "v$PhotoshopVersion" --repo $PHOTOSHOP_REPO --pattern "pyproject.toml" --dir "$env:TEMP" 2>$null
        $pyprojectPath = "$env:TEMP\pyproject.toml"
        if (Test-Path $pyprojectPath) {
            $content = Get-Content $pyprojectPath -Raw
            Remove-Item $pyprojectPath -Force
            if ($content -match 'dcc-mcp-core\s*>=\s*([\d.]+)') {
                return $matches[1]
            }
        }
    }
    catch {
        # Fall through
    }
    return $null
}

function Get-CoreVersionForPhotoshop {
    param([string]$PhotoshopVersion)
    # Try gh CLI download first (authenticated)
    $fromGh = Get-CoreVersionFromGhRelease -PhotoshopVersion $PhotoshopVersion
    if ($fromGh) { return $fromGh }

    # Fallback: download pyproject.toml via raw URL
    $url = "$RELEASE_BASE_PS/v$PhotoshopVersion/pyproject.toml"
    try {
        $content = Invoke-RestMethod -Uri $url -UseBasicParsing -Headers @{
            "User-Agent" = "dcc-mcp-installer/1.0"
        }
        if ($content -match 'dcc-mcp-core\s*>=\s*([\d.]+)') {
            return $matches[1]
        }
    }
    catch {
        Write-WarningMsg "Could not resolve core dependency from GitHub, will use latest"
    }
    return $null
}

function New-DirectoryIfAbsent {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        if (-not (Test-WhatIf "Create directory: $Path")) {
            New-Item -Path $Path -ItemType Directory -Force | Out-Null
            Write-Success "Created directory: $Path"
        }
    }
    else {
        Write-Info "Directory already exists: $Path"
    }
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination,
        [string]$Description
    )
    if ((Test-Path $Destination) -and -not $Force) {
        Write-Info "$Description already exists: $Destination (use -Force to overwrite)"
        return $false
    }
    if (Test-WhatIf "Download $Description from $Url to $Destination") {
        return $false
    }
    Write-Info "Downloading $Description from $Url"
    $parentDir = Split-Path $Destination -Parent
    New-DirectoryIfAbsent $parentDir
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -ErrorAction Stop
        Write-Success "Downloaded $Description"
        return $true
    }
    catch {
        Write-ErrorMsg "Failed to download $Description`: $_"
        if (Test-Path $Destination) { Remove-Item $Destination -Force }
        throw
    }
}

function Expand-ZipArchive {
    param(
        [string]$ZipPath,
        [string]$DestinationDir,
        [string]$BinaryName
    )
    if (Test-WhatIf "Extract $ZipPath to $DestinationDir\$BinaryName") {
        return
    }
    Write-Info "Extracting archive: $ZipPath"
    New-DirectoryIfAbsent $DestinationDir
    $tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
    try {
        Expand-Archive -Path $ZipPath -DestinationPath $tempExtract -Force
        $found = Get-ChildItem -Path $tempExtract -Recurse -Filter $BinaryName | Select-Object -First 1
        if ($found) {
            Copy-Item -Path $found.FullName -Destination "$DestinationDir\$BinaryName" -Force
            Write-Success "Extracted $BinaryName to $DestinationDir"
        }
        else {
            Write-WarningMsg "Binary $BinaryName not found in archive; copy all contents instead"
            Copy-Item -Path "$tempExtract\*" -Destination $DestinationDir -Recurse -Force
        }
    }
    finally {
        if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
    }
}

function Remove-FileIfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        if (-not (Test-WhatIf "Remove file: $Path")) {
            Remove-Item $Path -Force
            Write-Info "Removed: $Path"
        }
    }
}

# ── Version Helpers ──────────────────────────────────────────────────────────

function Get-InstalledVersion {
    <#
    .SYNOPSIS
        Read the installed version from .version file in the binary directory.
    #>
    $versionFile = "$BIN_DIR\.version"
    if (Test-Path $versionFile) {
        try {
            return (Get-Content $versionFile -Raw -ErrorAction Stop).Trim()
        }
        catch {
            return $null
        }
    }
    return $null
}

function Write-VersionFile {
    param([string]$Version)
    $versionFile = "$BIN_DIR\.version"
    if (-not (Test-WhatIf "Write version file: $versionFile = $Version")) {
        $Version | Out-File -FilePath $versionFile -Encoding utf8 -Force
        Write-Success "Wrote version file: $versionFile"
    }
}

# ── Backup & Process Helpers ────────────────────────────────────────────────

function Backup-Binaries {
    <#
    .SYNOPSIS
        Backup current binaries to the .rollback directory before upgrade.
    #>
    $rollbackDir = "$BIN_DIR\.rollback"
    New-DirectoryIfAbsent $rollbackDir

    $binaries = @($PHOTOSHOP_BINARY, $SERVER_BINARY)
    $backedUp = $false
    foreach ($binary in $binaries) {
        $src = "$BIN_DIR\$binary"
        $dst = "$rollbackDir\$binary"
        if (Test-Path $src) {
            if (-not (Test-WhatIf "Backup $binary to $rollbackDir")) {
                Copy-Item -Path $src -Destination $dst -Force
                Write-Success "Backed up $binary to rollback"
                $backedUp = $true
            }
        }
    }

    # Backup version info
    $versionFile = "$BIN_DIR\.version"
    $backupVersionFile = "$rollbackDir\.version"
    if (Test-Path $versionFile) {
        if (-not (Test-WhatIf "Backup .version to rollback")) {
            Copy-Item -Path $versionFile -Destination $backupVersionFile -Force
        }
    }

    if ($backedUp) {
        Write-Success "Backup complete (rollback dir: $rollbackDir)"
    }
    else {
        Write-Info "No existing binaries to backup"
    }
}

function Stop-DccMcpProcesses {
    <#
    .SYNOPSIS
        Stop any running dcc-mcp processes (server and photoshop bridge).
    #>
    $processNames = @(
        [System.IO.Path]::GetFileNameWithoutExtension($PHOTOSHOP_BINARY),
        [System.IO.Path]::GetFileNameWithoutExtension($SERVER_BINARY)
    )

    $stopped = $false
    foreach ($name in $processNames) {
        $running = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($proc in $running) {
            if (Test-WhatIf "Stop process $name (PID: $($proc.Id))") { continue }
            Write-Info "Stopping $name (PID: $($proc.Id))..."
            try {
                $proc.Kill()
                $proc.WaitForExit(5000)
                Write-Success "Stopped $name (PID: $($proc.Id))"
                $stopped = $true
            }
            catch {
                Write-WarningMsg "Failed to stop $name gracefully: $_"
                try { taskkill /f /im "$name.exe" 2>$null | Out-Null } catch {}
                $stopped = $true
            }
        }
    }

    if (-not $stopped) {
        Write-Info "No running dcc-mcp processes found"
    }
}

# ── Step Functions ───────────────────────────────────────────────────────────

function Install-Binaries {
    Write-Info "=== Step 1: Install/Upgrade Binaries ==="

    # Resolve versions
    if ($script:WhatIfMode) {
        $resolvedVersion = $Version
        if (-not $resolvedVersion) { $resolvedVersion = "<latest>" }
        $resolvedCoreVersion = $CoreVersion
        if (-not $resolvedCoreVersion) { $resolvedCoreVersion = "<latest>" }
    }
    else {
        if (-not $Version) {
            $resolvedVersion = Get-LatestReleaseVersion -Repo $PHOTOSHOP_REPO
            Write-Info "Resolved dcc-mcp-photoshop version: $resolvedVersion"
        }
        else {
            $resolvedVersion = $Version
        }

        if (-not $CoreVersion) {
            $resolvedCoreVersion = Get-CoreVersionForPhotoshop -PhotoshopVersion $resolvedVersion
            if (-not $resolvedCoreVersion) {
                $latestCore = Get-LatestReleaseVersion -Repo $CORE_REPO
                Write-WarningMsg "Falling back to latest dcc-mcp-core version: $latestCore"
                $resolvedCoreVersion = $latestCore
            }
            else {
                Write-Info "Resolved dcc-mcp-core version: $resolvedCoreVersion"
            }
        }
        else {
            $resolvedCoreVersion = $CoreVersion
        }
    }

    New-DirectoryIfAbsent $BIN_DIR

    # Download dcc-mcp-photoshop binary (standalone .exe)
    $psUrl = "$RELEASE_BASE_PS/v$resolvedVersion/$PHOTOSHOP_BINARY"
    $psDest = "$BIN_DIR\$PHOTOSHOP_BINARY"
    $null = Download-File -Url $psUrl -Destination $psDest -Description "dcc-mcp-photoshop binary"

    # Download dcc-mcp-server binary (standalone .exe)
    $serverUrl = "$RELEASE_BASE_CORE/v$resolvedCoreVersion/$SERVER_BINARY"
    $serverDest = "$BIN_DIR\$SERVER_BINARY"
    $null = Download-File -Url $serverUrl -Destination $serverDest -Description "dcc-mcp-server binary"

    # Write version file
    Write-VersionFile -Version $resolvedVersion

    Write-Success "Binary installation complete (version photoshop=$resolvedVersion, core=$resolvedCoreVersion)"
}

function Install-CcxPlugin {
    Write-Info "=== Step 2: Install .ccx Plugin ==="

    if ($script:WhatIfMode) {
        $null = Test-WhatIf "Download UXP .ccx plugin from GitHub Releases to $UXP_DIR"
        Write-Success "Plugin installation complete"
        return
    }

    if (-not $Version) {
        $resolvedVersion = Get-LatestReleaseVersion -Repo $PHOTOSHOP_REPO
    }
    else {
        $resolvedVersion = $Version
    }

    $pluginFileName = $PLUGIN_FILE -f $resolvedVersion
    $pluginUrl = "$RELEASE_BASE_PS/v$resolvedVersion/$pluginFileName"
    $pluginDest = "$env:TEMP\$pluginFileName"
    $uxpDest = "$UXP_DIR\$pluginFileName"

    $downloaded = Download-File -Url $pluginUrl -Destination $pluginDest -Description "UXP .ccx plugin"

    if ($downloaded -or $Force) {
        New-DirectoryIfAbsent $UXP_DIR
        if (Test-Path $uxpDest) {
            if ($Force) {
                Remove-Item $uxpDest -Force
            }
            else {
                throw "Plugin already exists at $uxpDest. Use -Force to overwrite."
            }
        }
        if (-not (Test-WhatIf "Copy .ccx to $uxpDest")) {
            Copy-Item -Path $pluginDest -Destination $uxpDest -Force
            Write-Success "Installed .ccx plugin to $uxpDest"
        }
    }
    else {
        Write-Info "Plugin already up-to-date at $uxpDest"
    }

    Write-Success "Plugin installation complete"
}

function Write-LocalConfig {
    Write-Info "=== Step 3: Write Local Configuration ==="

    New-DirectoryIfAbsent $REGISTRY_DIR
    New-DirectoryIfAbsent $CONFIG_DIR

    $bridgeConfig = @"
{
    "version": 1,
    "dcc": "photoshop",
    "bin_dir": "$( $BIN_DIR -replace '\\', '\\' )",
    "mcp_port": 8765,
    "ws_port": 9001,
    "gateway_port": 9765,
    "rpc_port": 9100,
    "registry_dir": "$( $REGISTRY_DIR -replace '\\', '\\' )",
    "photoshop_binary": "$PHOTOSHOP_BINARY",
    "server_binary": "$SERVER_BINARY",
    "autostart": $(-not $NoAutostart)
}
"@

    $configFile = "$CONFIG_DIR\bridge.json"
    if (Test-WhatIf "Write bridge config to $configFile") {
        return
    }

    # Preserve existing config if not -Force
    if ((Test-Path $configFile) -and -not $Force) {
        Write-Info "Config already exists: $configFile (use -Force to overwrite)"
    }
    else {
        $bridgeConfig | Out-File -FilePath $configFile -Encoding utf8 -Force
        Write-Success "Wrote bridge config: $configFile"
    }

    Write-Success "Local configuration complete"
}

function Register-Autostart {
    Write-Info "=== Step 4: Register Autostart ==="
    if ($NoAutostart) {
        Write-Info "Skipping autostart registration (-NoAutostart specified)"
        return
    }

    $autostartScript = "$BIN_DIR\$AUTOSTART_SCRIPT_NAME"
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $runValueName = "DCC-MCP Photoshop"

    # Generate autostart launcher script
    $scriptContent = @"
@echo off
setlocal
cd /d "%~dp0"
echo [%date% %time%] Starting dcc-mcp Photoshop connector... >> "%~dp0autostart.log"
start "" "%~dp0$SERVER_BINARY" --dcc photoshop --mcp-port 8765 --ws-port 9001 --gateway-port 9765 --registry-dir "%USERPROFILE%\.dcc-mcp\registry" >> "%~dp0autostart.log" 2>&1
"@

    if (-not (Test-WhatIf "Write autostart script: $autostartScript")) {
        $scriptContent | Out-File -FilePath $autostartScript -Encoding default -Force
        Write-Success "Wrote autostart script: $autostartScript"
    }

    if (-not (Test-WhatIf "Register HKCU Run key '$runValueName' -> $autostartScript")) {
        if (-not (Test-Path $runKey)) {
            New-Item -Path $runKey -Force | Out-Null
        }
        Set-ItemProperty -Path $runKey -Name $runValueName -Value $autostartScript
        Write-Success "Registered autostart: $runKey\$runValueName"
    }

    Write-Success "Autostart registration complete"
}

function Invoke-SmokeCheck {
    Write-Info "=== Step 5: Smoke Check ==="
    if ($NoSmoke) {
        Write-Info "Skipping smoke check (-NoSmoke specified)"
        return
    }

    # Check that binaries exist
    $psBinary = "$BIN_DIR\$PHOTOSHOP_BINARY"
    $serverBinary = "$BIN_DIR\$SERVER_BINARY"
    if (-not (Test-Path $psBinary)) {
        Write-ErrorMsg "Binary not found: $psBinary. Run install first."
        return
    }
    if (-not (Test-Path $serverBinary)) {
        Write-ErrorMsg "Binary not found: $serverBinary. Run install first."
        return
    }
    if ($WhatIf) {
        Write-Host "[WHATIF] Would start binaries and run smoke checks" -ForegroundColor Magenta
        return
    }

    # Start dcc-mcp-server in host-rpc mode
    Write-Info "Starting dcc-mcp-server (host-rpc mode) for smoke check..."
    $serverLog = "$BIN_DIR\smoke-server.log"
    $serverProcess = Start-Process -FilePath $serverBinary -ArgumentList @(
        "--dcc", "photoshop",
        "--mcp-port", "8765",
        "--ws-port", "9001",
        "--gateway-port", "9765",
        "--rpc-port", "9100",
        "--registry-dir", $REGISTRY_DIR
    ) -NoNewWindow -PassThru -RedirectStandardOutput $serverLog -RedirectStandardError $serverLog

    Write-Info "Server started (PID: $($serverProcess.Id)), waiting for it to become ready..."

    # Wait for the gateway health endpoint
    $healthOk = $false
    $maxRetries = 30
    $retryDelay = 1  # seconds
    for ($i = 0; $i -lt $maxRetries; $i++) {
        Start-Sleep -Seconds $retryDelay
        try {
            $response = Invoke-RestMethod -Uri $GATEWAY_HEALTH_URL -UseBasicParsing -TimeoutSec 2
            Write-Success "Gateway health check passed: $($response | ConvertTo-Json -Compress)"
            $healthOk = $true
            break
        }
        catch {
            if ($i -lt $maxRetries - 1) {
                Write-Info "  Health check attempt $($i+1): not ready yet..."
            }
            else {
                Write-WarningMsg "Gateway health check failed after $maxRetries attempts: $_"
            }
        }
    }

    # Wait for the bridge RPC health endpoint
    $rpcOk = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-RestMethod -Uri $RPC_URL -UseBasicParsing -TimeoutSec 2
            Write-Success "Bridge RPC health check passed: $($response | ConvertTo-Json -Compress)"
            $rpcOk = $true
            break
        }
        catch {
            if ($i -lt 14) {
                Write-Info "  RPC health check attempt $($i+1): not ready yet..."
            }
            else {
                Write-WarningMsg "Bridge RPC health check failed after 15 attempts: $_"
            }
        }
    }

    # Summary
    if ($healthOk -and $rpcOk) {
        Write-Success "Smoke check passed: gateway and bridge RPC are healthy"
    }
    elseif ($healthOk) {
        Write-WarningMsg "Smoke check partial: gateway OK but bridge RPC unreachable"
    }
    else {
        Write-WarningMsg "Smoke check failed: gateway unreachable"
        Write-Info "Check server log: $serverLog"
    }

    # Stop the server
    Write-Info "Stopping smoke test server (PID: $($serverProcess.Id))..."
    try {
        $serverProcess.Kill()
        $serverProcess.WaitForExit(5000)
        Write-Success "Smoke test server stopped"
    }
    catch {
        Write-WarningMsg "Failed to stop server cleanly: $_"
        try { taskkill /f /im $SERVER_BINARY | Out-Null } catch {}
    }
}

# ── Mode Functions ───────────────────────────────────────────────────────────

function Invoke-Upgrade {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " dcc-mcp Photoshop Connector Upgrade" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    # Check current installation
    $psBinary = "$BIN_DIR\$PHOTOSHOP_BINARY"
    $serverBinary = "$BIN_DIR\$SERVER_BINARY"
    $installed = (Test-Path $psBinary) -or (Test-Path $serverBinary)

    if (-not $installed) {
        Write-Info "No existing installation found at $BIN_DIR. Running fresh install instead."
        Install-Binaries
        Install-CcxPlugin
        Write-LocalConfig
        Register-Autostart
        Invoke-SmokeCheck
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Green
        Write-Success "Fresh installation complete (no previous version to upgrade)!"
        return
    }

    # Backup existing binaries
    Write-Info "=== Step 1: Backup Existing Binaries ==="
    Backup-Binaries
    Write-Host ""

    # Stop running processes so binaries can be replaced
    Write-Info "=== Step 2: Stop Running Processes ==="
    Stop-DccMcpProcesses
    Write-Host ""

    # Remove old binaries so Download-File fetches fresh copies
    Write-Info "=== Step 3: Remove Old Binaries ==="
    foreach ($binary in @($PHOTOSHOP_BINARY, $SERVER_BINARY)) {
        Remove-FileIfExists "$BIN_DIR\$binary"
    }
    Write-Host ""

    # Install new version
    Write-Info "=== Step 4: Install New Binaries ==="
    Install-Binaries
    Write-Host ""

    # Update plugin
    Write-Info "=== Step 5: Update Plugin ==="
    Install-CcxPlugin
    Write-Host ""

    # Config and autostart are preserved (not overwritten)
    Write-Info "=== Step 6: Register Autostart ==="
    Register-Autostart
    Write-Host ""

    # Smoke check
    Write-Info "=== Step 7: Smoke Check ==="
    Invoke-SmokeCheck
    Write-Host ""

    Write-Host "============================================" -ForegroundColor Green
    Write-Success "Upgrade complete!"
    Write-Host ""
    Write-Host "  Previous version backed up to: $BIN_DIR\.rollback"
    Write-Host "  Use -Rollback to restore the previous version."
    Write-Host "============================================" -ForegroundColor Green
}

function Invoke-Uninstall {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " dcc-mcp Photoshop Connector Uninstall" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    # Stop running processes
    Write-Info "=== Step 1: Stop Running Processes ==="
    Stop-DccMcpProcesses
    Write-Host ""

    # Remove HKCU Run key
    Write-Info "=== Step 2: Remove Autostart Registry Key ==="
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $runValueName = "DCC-MCP Photoshop"
    if (Test-Path "$runKey") {
        try {
            $currentValue = Get-ItemProperty -Path $runKey -Name $runValueName -ErrorAction SilentlyContinue
            if ($currentValue) {
                if (-not (Test-WhatIf "Remove HKCU Run key '$runValueName'")) {
                    Remove-ItemProperty -Path $runKey -Name $runValueName -ErrorAction Stop
                    Write-Success "Removed autostart registry key: $runKey\$runValueName"
                }
            }
            else {
                Write-Info "No autostart registry key found: $runValueName"
            }
        }
        catch {
            Write-Info "No autostart registry key found: $runValueName"
        }
    }
    else {
        Write-Info "Registry key path does not exist: $runKey"
    }
    Write-Host ""

    # Remove autostart script
    Write-Info "=== Step 3: Remove Autostart Script ==="
    $autostartScript = "$BIN_DIR\$AUTOSTART_SCRIPT_NAME"
    Remove-FileIfExists $autostartScript
    Write-Host ""

    # Clean binary directory
    Write-Info "=== Step 4: Clean Binary Directory ==="
    if (Test-Path $BIN_DIR) {
        if (-not (Test-WhatIf "Remove binary directory contents: $BIN_DIR")) {
            # Remove everything except .rollback backup
            Get-ChildItem -Path $BIN_DIR -Exclude ".rollback" | ForEach-Object {
                Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Success "Cleaned binary directory: $BIN_DIR"
        }
    }
    else {
        Write-Info "Binary directory does not exist: $BIN_DIR"
    }
    Write-Host ""

    # Optionally remove configuration
    if (-not $KeepConfig) {
        Write-Info "=== Step 5: Clean Configuration ==="
        $configDirs = @{ "Config" = $CONFIG_DIR; "Registry" = $REGISTRY_DIR }
        foreach ($label in $configDirs.Keys) {
            $dir = $configDirs[$label]
            if (Test-Path $dir) {
                if (-not (Test-WhatIf "Remove $label directory: $dir")) {
                    Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
                    Write-Success "Removed ${label}: $dir"
                }
            }
            else {
                Write-Info "$label directory does not exist: $dir"
            }
        }
        # Also clean UXP plugin
        $pluginFileName = if ($Version) { $PLUGIN_FILE -f $Version } else { $PLUGIN_FILE -f "*" }
        $uxpFiles = Get-ChildItem -Path $UXP_DIR -Filter "dcc-mcp-photoshop-bridge-*.ccx" -ErrorAction SilentlyContinue
        if ($uxpFiles) {
            if (-not (Test-WhatIf "Remove UXP plugin files from $UXP_DIR")) {
                $uxpFiles | Remove-Item -Force -ErrorAction SilentlyContinue
                Write-Success "Removed UXP plugin files from $UXP_DIR"
            }
        }
        Write-Host ""
    }
    else {
        Write-Info "Configuration preserved (-KeepConfig specified)"
        Write-Host ""
    }

    Write-Host "============================================" -ForegroundColor Green
    Write-Success "Uninstall complete!"
    if ($KeepConfig) {
        Write-Host ""
        Write-Host "  Configuration preserved at:"
        Write-Host "    Config:  $CONFIG_DIR"
        Write-Host "    Registry: $REGISTRY_DIR"
    }
    Write-Host "============================================" -ForegroundColor Green
}

function Invoke-Rollback {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " dcc-mcp Photoshop Connector Rollback" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    $rollbackDir = "$BIN_DIR\.rollback"

    # Verify rollback backup exists
    if (-not (Test-Path $rollbackDir)) {
        Write-ErrorMsg "No rollback backup found at $rollbackDir"
        Write-ErrorMsg "Upgrade must be performed before rollback is available."
        exit 1
    }

    # Check for backup content
    $binaries = @($PHOTOSHOP_BINARY, $SERVER_BINARY)
    $hasBackup = $false
    foreach ($binary in $binaries) {
        if (Test-Path "$rollbackDir\$binary") {
            $hasBackup = $true
            break
        }
    }

    if (-not $hasBackup) {
        Write-ErrorMsg "Rollback backup exists but contains no binary files at $rollbackDir"
        exit 1
    }

    # Read rollback version info
    $rollbackVersionFile = "$rollbackDir\.version"
    if (Test-Path $rollbackVersionFile) {
        try {
            $rollbackVersion = (Get-Content $rollbackVersionFile -Raw -ErrorAction Stop).Trim()
            Write-Info "Rollback target version: $rollbackVersion"
        }
        catch {
            Write-Info "Rollback target version: unknown (no .version file in backup)"
        }
    }
    else {
        Write-Info "Rollback target version: unknown"
    }
    Write-Host ""

    # Stop running processes
    Write-Info "=== Step 1: Stop Running Processes ==="
    Stop-DccMcpProcesses
    Write-Host ""

    # Restore binaries from backup
    Write-Info "=== Step 2: Restore Binaries from Backup ==="
    Write-Info "Restoring from: $rollbackDir"

    foreach ($binary in $binaries) {
        $backupFile = "$rollbackDir\$binary"
        $destFile = "$BIN_DIR\$binary"
        if (Test-Path $backupFile) {
            if (-not (Test-WhatIf "Restore $binary from rollback backup")) {
                Copy-Item -Path $backupFile -Destination $destFile -Force
                Write-Success "Restored $binary"
            }
        }
        else {
            # Remove the current binary if no backup exists for it
            Remove-FileIfExists $destFile
            Write-Info "No rollback backup for $binary; removed current binary"
        }
    }

    # Restore version file
    if (Test-Path $rollbackVersionFile) {
        if (-not (Test-WhatIf "Restore .version file from rollback backup")) {
            Copy-Item -Path $rollbackVersionFile -Destination "$BIN_DIR\.version" -Force
        }
    }
    else {
        Remove-FileIfExists "$BIN_DIR\.version"
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Success "Rollback complete!"
    Write-Host ""
    Write-Host "  Previous version restored from: $rollbackDir"
    Write-Host "============================================" -ForegroundColor Green
}

# ── Main ─────────────────────────────────────────────────────────────────────

function Invoke-VersionCheck {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " dcc-mcp Photoshop Connector Version Check" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    $installedVersion = Get-InstalledVersion
    if ($installedVersion) {
        Write-Success "Local installed version: $installedVersion"
    }
    else {
        Write-Info "Local installed version: not found (not installed yet)"
    }

    # Check remote latest
    if (-not $script:WhatIfMode) {
        try {
            $latestVersion = Get-LatestReleaseVersion -Repo $PHOTOSHOP_REPO
            Write-Success "Remote latest version: $latestVersion"

            if ($installedVersion -and $latestVersion) {
                if ($installedVersion -eq $latestVersion) {
                    Write-Success "You have the latest version ($latestVersion)"
                }
                else {
                    Write-WarningMsg "A newer version is available: $latestVersion (installed: $installedVersion)"
                    Write-Host ""
                    Write-Host "  To upgrade, run:" -ForegroundColor Yellow
                    Write-Host "    .\install_photoshop_connector.ps1 -Upgrade" -ForegroundColor Yellow
                }
            }
        }
        catch {
            Write-ErrorMsg "Failed to check remote version: $_"
        }
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
}

function Main {
    # Dispatch to mode-specific function
    switch ($PSCmdlet.ParameterSetName) {
        "Check" {
            Invoke-VersionCheck
            return
        }
        "Upgrade" {
            Invoke-Upgrade
            return
        }
        "Uninstall" {
            Invoke-Uninstall
            return
        }
        "Rollback" {
            Invoke-Rollback
            return
        }
    }

    # Default: Install
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " dcc-mcp Photoshop Connector Installer" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    # Validate OS
    if ($env:OS -ne "Windows_NT") {
        Write-ErrorMsg "This installer only supports Windows"
        exit 1
    }

    if ($WhatIf) {
        Write-Host "[WHATIF] Mode: no changes will be made" -ForegroundColor Magenta
        Write-Host ""
    }

    Install-Binaries
    Write-Host ""

    Install-CcxPlugin
    Write-Host ""

    Write-LocalConfig
    Write-Host ""

    Register-Autostart
    Write-Host ""

    Invoke-SmokeCheck
    Write-Host ""

    Write-Host "============================================" -ForegroundColor Green
    Write-Success "Installation complete!"
    Write-Host ""
    Write-Host "  Binaries:    $BIN_DIR"
    Write-Host "  Config:      $CONFIG_DIR\bridge.json"
    Write-Host "  Registry:    $REGISTRY_DIR"
    Write-Host "  Plugin:      $UXP_DIR"
    Write-Host ""
    Write-Host "  Next steps:"
    Write-Host "    1. Restart Photoshop to load the UXP plugin"
    Write-Host "    2. Run 'dcc-mcp-server --dcc photoshop --mcp-port 8765 --ws-port 9001'"
    Write-Host "    3. Connect your MCP client to http://127.0.0.1:9765/mcp"
    if (-not $NoAutostart) {
        Write-Host ""
        Write-Host "  Autostart is enabled. The connector will start automatically with Windows."
    }
    Write-Host "============================================" -ForegroundColor Green
}

Main
