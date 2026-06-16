<#
.SYNOPSIS
    Install or upgrade the dcc-mcp Photoshop connector on Windows.

.DESCRIPTION
    All-in-one installer that downloads, configures, and smoke-tests
    the dcc-mcp Photoshop connector. Performs the following steps:

    1. Install/upgrade binaries (dcc-mcp-photoshop + dcc-mcp-server)
       from GitHub Releases to $env:LOCALAPPDATA\dcc-mcp\bin\
    2. Install the UXP .ccx plugin into Photoshop's external plugin dir
    3. Write local registry directory and bridge configuration
    4. Register autostart via HKCU Run key
    5. Optional smoke check: start server, verify gateway health + bridge

.PARAMETER Install
    Default action; install or upgrade the connector.

.PARAMETER Version
    Semantic version of dcc-mcp-photoshop to install (e.g. "0.1.18").
    Defaults to the latest release if not specified.

.PARAMETER CoreVersion
    Semantic version of dcc-mcp-core (dcc-mcp-server) to install.
    Defaults to the version pinned by the photoshop release's dependency
    constraint, or the latest if unresolved.

.PARAMETER NoAutostart
    Skip registering the connector to start automatically with Windows.

.PARAMETER NoSmoke
    Skip the post-install smoke check.

.PARAMETER WhatIf
    Show what would be done without making any changes.

.PARAMETER Force
    Overwrite existing files without prompting.

.EXAMPLE
    .\install_photoshop_connector.ps1 -Install

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

    [Parameter()]
    [string]$Version,

    [Parameter()]
    [string]$CoreVersion,

    [Parameter()]
    [switch]$NoAutostart,

    [Parameter()]
    [switch]$NoSmoke,

    [Parameter()]
    [switch]$Force
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

# ── Main ─────────────────────────────────────────────────────────────────────

function Main {
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
