[CmdletBinding()]
param(
    [ValidateSet("Menu", "Start", "Stop", "Status", "Open", "Logs", "InstallShortcuts")]
    [string]$Action = "Menu",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$script:ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:RuntimeRoot = Join-Path $script:ProjectRoot ".stone-runtime"
$script:LogsRoot = Join-Path $script:RuntimeRoot "logs"
$script:StateFile = Join-Path $script:RuntimeRoot "processes.json"
$script:ControllerLog = Join-Path $script:LogsRoot "controller.log"
$script:BackendPort = 8000
$script:FrontendPort = 5173

function Write-Heading {
    param([string]$Text)

    Write-Host ""
    Write-Host ("=" * 68) -ForegroundColor DarkCyan
    Write-Host ("  {0}" -f $Text) -ForegroundColor Cyan
    Write-Host ("=" * 68) -ForegroundColor DarkCyan
}

function Initialize-Runtime {
    New-Item -ItemType Directory -Path $script:LogsRoot -Force | Out-Null
}

function Write-ControllerEvent {
    param(
        [string]$Level,
        [string]$Message
    )

    Initialize-Runtime
    $line = "{0} [{1}] {2}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Add-Content -LiteralPath $script:ControllerLog -Value $line -Encoding UTF8
}

function New-EmptyState {
    [pscustomobject]@{
        Version = 1
        ProjectRoot = $script:ProjectRoot
        Backend = $null
        Frontend = $null
    }
}

function Get-LauncherState {
    Initialize-Runtime
    if (-not (Test-Path -LiteralPath $script:StateFile -PathType Leaf)) {
        return New-EmptyState
    }

    try {
        $state = Get-Content -LiteralPath $script:StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $state.ProjectRoot -or
            -not [string]::Equals(
                [System.IO.Path]::GetFullPath([string]$state.ProjectRoot).TrimEnd("\"),
                $script:ProjectRoot.TrimEnd("\"),
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
            throw "The state file belongs to a different project location."
        }
        return $state
    }
    catch {
        $backup = "{0}.invalid-{1}" -f $script:StateFile, (Get-Date).ToString("yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $script:StateFile -Destination $backup -Force
        Write-Warning "The launcher state was invalid and has been preserved as '$backup'."
        Write-ControllerEvent "WARN" "Invalid state file moved aside."
        return New-EmptyState
    }
}

function Save-LauncherState {
    param([Parameter(Mandatory)]$State)

    Initialize-Runtime
    $temporaryFile = Join-Path $script:RuntimeRoot ("processes-{0}.tmp" -f [guid]::NewGuid().ToString("N"))
    $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporaryFile -Encoding UTF8
    Move-Item -LiteralPath $temporaryFile -Destination $script:StateFile -Force
}

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match ("^\s*{0}\s*=\s*(.*?)\s*$" -f [regex]::Escape($Name))) {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return $null
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $asyncResult = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Get-ListeningProcessId {
    param([Parameter(Mandatory)][int]$Port)

    try {
        $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
            Select-Object -First 1
        if ($connection) {
            return [int]$connection.OwningProcess
        }
    }
    catch {
        foreach ($line in (& "$env:SystemRoot\System32\netstat.exe" -ano -p tcp 2>$null)) {
            if ($line -match ("^\s*TCP\s+\S+:{0}\s+\S+\s+LISTENING\s+(\d+)\s*$" -f $Port)) {
                return [int]$Matches[1]
            }
        }
    }

    return $null
}

function Assert-MySqlConfiguration {
    $environmentFile = Join-Path $script:ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
        throw "Missing .env file. Complete the installation guide before starting the application."
    }

    $databaseUrl = Get-DotEnvValue -Name "DATABASE_URL" -Path $environmentFile
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        throw "DATABASE_URL is missing from .env."
    }
    if ($databaseUrl -notmatch "^mysql\+pymysql://") {
        throw "DATABASE_URL must begin with 'mysql+pymysql://'. This launcher will not start with another database driver."
    }

    $hostName = Get-DotEnvValue -Name "MYSQL_HOST" -Path $environmentFile
    $portText = Get-DotEnvValue -Name "MYSQL_PORT" -Path $environmentFile
    if ($databaseUrl -match "^mysql\+pymysql://(?:.*@)?(?<host>[^:/?]+)(?::(?<port>\d+))?/") {
        if ([string]::IsNullOrWhiteSpace($hostName)) {
            $hostName = $Matches["host"]
        }
        if ([string]::IsNullOrWhiteSpace($portText) -and $Matches["port"]) {
            $portText = $Matches["port"]
        }
    }
    if ([string]::IsNullOrWhiteSpace($hostName)) {
        $hostName = "127.0.0.1"
    }
    $mysqlPort = 3306
    if (-not [string]::IsNullOrWhiteSpace($portText)) {
        $parsedPort = 0
        if (-not [int]::TryParse($portText, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
            throw "MYSQL_PORT in .env is invalid."
        }
        $mysqlPort = $parsedPort
    }

    [pscustomobject]@{
        HostName = $hostName
        Port = $mysqlPort
    }
}

function Ensure-MySqlAvailable {
    param([Parameter(Mandatory)]$MySqlConfiguration)

    $hostName = [string]$MySqlConfiguration.HostName
    $mysqlPort = [int]$MySqlConfiguration.Port
    if (Test-TcpPort -HostName $hostName -Port $mysqlPort -TimeoutMilliseconds 1200) {
        Write-Host ("[OK] MySQL is available at {0}:{1}." -f $hostName, $mysqlPort) -ForegroundColor Green
        return
    }

    $isLocal = $hostName -in @("127.0.0.1", "localhost", "::1")
    if (-not $isLocal) {
        throw "MySQL at ${hostName}:$mysqlPort is not reachable. Start the remote database and try again."
    }

    $service = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
    if (-not $service) {
        $service = Get-Service -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "MySQL*" } |
            Sort-Object @{ Expression = { if ($_.Status -eq "Running") { 0 } else { 1 } } }, Name |
            Select-Object -First 1
    }
    if (-not $service) {
        throw "No local MySQL Windows service was found. Install MySQL 8.0 or update DATABASE_URL."
    }

    if ($service.Status -ne "Running") {
        Write-Host ("Starting Windows service '{0}'..." -f $service.Name) -ForegroundColor Yellow
        try {
            Start-Service -Name $service.Name -ErrorAction Stop
        }
        catch {
            Write-Host "Administrator approval is required to start MySQL." -ForegroundColor Yellow
            $escapedServiceName = $service.Name.Replace("'", "''")
            $elevatedCommand = "Start-Service -Name '$escapedServiceName'"
            try {
                $elevated = Start-Process -FilePath "powershell.exe" `
                    -ArgumentList @("-NoProfile", "-Command", $elevatedCommand) `
                    -Verb RunAs -Wait -PassThru
                if ($elevated.ExitCode -ne 0) {
                    throw "The elevated MySQL start command failed."
                }
            }
            catch {
                throw "MySQL could not be started. Start service '$($service.Name)' as Administrator and try again."
            }
        }
    }

    Write-Host "Waiting for MySQL" -NoNewline
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        if (Test-TcpPort -HostName $hostName -Port $mysqlPort -TimeoutMilliseconds 800) {
            Write-Host ""
            Write-Host "[OK] MySQL is ready." -ForegroundColor Green
            return
        }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 1
    }
    Write-Host ""
    throw "MySQL did not become ready within 45 seconds."
}

function Assert-Prerequisites {
    $pythonPath = Join-Path $script:ProjectRoot "backend\venv\Scripts\python.exe"
    $viteScript = Join-Path $script:ProjectRoot "frontend\node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw "Python environment not found at 'backend\venv'. Follow the installation guide first."
    }
    if (-not (Test-Path -LiteralPath $viteScript -PathType Leaf)) {
        throw "Frontend packages are missing. Run 'npm.cmd install' inside the frontend folder."
    }

    $nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
    if (-not $nodeCommand) {
        throw "Node.js is not installed or is not available in PATH."
    }
    $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npmCommand) {
        throw "npm is not installed or is not available in PATH."
    }

    [pscustomobject]@{
        PythonPath = [System.IO.Path]::GetFullPath($pythonPath)
        NodePath = [System.IO.Path]::GetFullPath($nodeCommand.Source)
        NpmPath = [System.IO.Path]::GetFullPath($npmCommand.Source)
        ViteScript = [System.IO.Path]::GetFullPath($viteScript)
    }
}

function Get-VerifiedManagedProcess {
    param(
        $Entry,
        [Parameter(Mandatory)][string]$Role,
        [switch]$Quiet
    )

    if (-not $Entry -or -not $Entry.Pid -or -not $Entry.StartedAtUtc -or -not $Entry.Executable) {
        return $null
    }
    if (-not [string]::Equals(
        [string]$Entry.ProjectRoot,
        $script:ProjectRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        if (-not $Quiet) {
            Write-Warning "$Role state belongs to a different project directory; no process was touched."
        }
        return $null
    }

    try {
        $process = Get-Process -Id ([int]$Entry.Pid) -ErrorAction Stop
        $actualStartedAt = $process.StartTime.ToUniversalTime()
        $recordedStartedAt = [DateTime]::Parse(
            [string]$Entry.StartedAtUtc,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        ).ToUniversalTime()
        if ([Math]::Abs(($actualStartedAt - $recordedStartedAt).TotalSeconds) -gt 3) {
            if (-not $Quiet) {
                Write-Warning "$Role PID was reused by another process; it was not touched."
            }
            return $null
        }

        $actualExecutable = [System.IO.Path]::GetFullPath($process.Path)
        $recordedExecutable = [System.IO.Path]::GetFullPath([string]$Entry.Executable)
        if (-not [string]::Equals(
            $actualExecutable,
            $recordedExecutable,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            if (-not $Quiet) {
                Write-Warning "$Role executable does not match the launcher record; it was not touched."
            }
            return $null
        }

        $processInfo = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f [int]$Entry.Pid) `
            -ErrorAction SilentlyContinue
        if ($Entry.CommandToken -and
            $processInfo -and
            $processInfo.CommandLine -and
            $processInfo.CommandLine.IndexOf(
                [string]$Entry.CommandToken,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -lt 0) {
            if (-not $Quiet) {
                Write-Warning "$Role command line does not match the launcher record; it was not touched."
            }
            return $null
        }
        return $process
    }
    catch {
        return $null
    }
}

function New-ProcessEntry {
    param(
        [Parameter(Mandatory)]$Process,
        [Parameter(Mandatory)][string]$Role,
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string]$CommandToken,
        [Parameter(Mandatory)][string]$StandardOutputLog,
        [Parameter(Mandatory)][string]$StandardErrorLog
    )

    [pscustomobject]@{
        Role = $Role
        Pid = [int]$Process.Id
        StartedAtUtc = $Process.StartTime.ToUniversalTime().ToString("o")
        Executable = [System.IO.Path]::GetFullPath($Executable)
        CommandToken = $CommandToken
        ProjectRoot = $script:ProjectRoot
        StandardOutputLog = $StandardOutputLog
        StandardErrorLog = $StandardErrorLog
    }
}

function Stop-VerifiedProcessTree {
    param(
        [Parameter(Mandatory)]$Entry,
        [Parameter(Mandatory)][string]$Role
    )

    $rootProcess = Get-VerifiedManagedProcess -Entry $Entry -Role $Role
    if (-not $rootProcess) {
        Write-Host ("[SKIP] {0} is not a verified launcher-managed process." -f $Role) -ForegroundColor Yellow
        return $false
    }

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $pendingParents = New-Object System.Collections.Generic.Queue[int]
    $pendingParents.Enqueue([int]$rootProcess.Id)
    $descendants = New-Object System.Collections.Generic.List[int]
    while ($pendingParents.Count -gt 0) {
        $parentId = $pendingParents.Dequeue()
        foreach ($child in $allProcesses | Where-Object { [int]$_.ParentProcessId -eq $parentId }) {
            $childId = [int]$child.ProcessId
            $descendants.Add($childId)
            $pendingParents.Enqueue($childId)
        }
    }

    $childIds = @($descendants)
    [array]::Reverse($childIds)
    foreach ($childId in $childIds) {
        Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id ([int]$rootProcess.Id) -Force -ErrorAction Stop
    Write-Host ("[OK] {0} stopped." -f $Role) -ForegroundColor Green
    Write-ControllerEvent "INFO" "$Role stopped (PID $($rootProcess.Id))."
    return $true
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$Attempts = 40
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    }
    return $false
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][string]$Role
    )

    $ownerPid = Get-ListeningProcessId -Port $Port
    if ($ownerPid) {
        throw "$Role port $Port is already used by untracked PID $ownerPid. For safety, the launcher will not stop or replace it."
    }
}

function Start-StoneCrusher {
    Write-Heading "START STONE CRUSHER ERP"
    Initialize-Runtime
    $state = Get-LauncherState
    $backendProcess = Get-VerifiedManagedProcess -Entry $state.Backend -Role "Backend" -Quiet
    $frontendProcess = Get-VerifiedManagedProcess -Entry $state.Frontend -Role "Frontend" -Quiet
    $prerequisites = Assert-Prerequisites

    if (-not $backendProcess) {
        $state.Backend = $null
        Assert-PortAvailable -Port $script:BackendPort -Role "Backend"
    }
    if (-not $frontendProcess) {
        $state.Frontend = $null
        Assert-PortAvailable -Port $script:FrontendPort -Role "Frontend"
    }
    Save-LauncherState -State $state

    $mysqlConfiguration = Assert-MySqlConfiguration
    Ensure-MySqlAvailable -MySqlConfiguration $mysqlConfiguration

    $startedBackend = $false
    $startedFrontend = $false
    try {
        if (-not $backendProcess) {
            Write-Host "Applying database migrations..." -ForegroundColor Cyan
            Push-Location (Join-Path $script:ProjectRoot "backend")
            try {
                & $prerequisites.PythonPath -m alembic upgrade head
                if ($LASTEXITCODE -ne 0) {
                    throw "Database migration failed with exit code $LASTEXITCODE."
                }
            }
            finally {
                Pop-Location
            }

            $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
            $backendOut = Join-Path $script:LogsRoot "backend-$timestamp.out.log"
            $backendErr = Join-Path $script:LogsRoot "backend-$timestamp.err.log"
            $backendProcess = Start-Process -FilePath $prerequisites.PythonPath `
                -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$($script:BackendPort)") `
                -WorkingDirectory (Join-Path $script:ProjectRoot "backend") `
                -RedirectStandardOutput $backendOut `
                -RedirectStandardError $backendErr `
                -WindowStyle Hidden `
                -PassThru
            Start-Sleep -Milliseconds 400
            if ($backendProcess.HasExited) {
                throw "Backend exited during startup. See '$backendErr'."
            }
            $state.Backend = New-ProcessEntry `
                -Process $backendProcess `
                -Role "Backend" `
                -Executable $prerequisites.PythonPath `
                -CommandToken "app.main:app" `
                -StandardOutputLog $backendOut `
                -StandardErrorLog $backendErr
            Save-LauncherState -State $state
            $startedBackend = $true
            Write-Host ("[OK] Backend started (PID {0})." -f $backendProcess.Id) -ForegroundColor Green
            Write-ControllerEvent "INFO" "Backend started (PID $($backendProcess.Id))."
        }
        else {
            Write-Host ("[OK] Backend is already running (PID {0})." -f $backendProcess.Id) -ForegroundColor Green
        }

        if (-not (Wait-ForUrl -Url "http://127.0.0.1:$($script:BackendPort)/health" -Attempts 40)) {
            throw "Backend health check failed. Review the backend logs."
        }

        if (-not $frontendProcess) {
            $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
            $frontendOut = Join-Path $script:LogsRoot "frontend-$timestamp.out.log"
            $frontendErr = Join-Path $script:LogsRoot "frontend-$timestamp.err.log"
            $viteApiBaseUrl = Get-DotEnvValue -Name "VITE_API_BASE_URL" -Path (Join-Path $script:ProjectRoot ".env")
            $oldViteApiBaseUrl = $env:VITE_API_BASE_URL
            try {
                if (-not [string]::IsNullOrWhiteSpace($viteApiBaseUrl)) {
                    $env:VITE_API_BASE_URL = $viteApiBaseUrl
                }
                # Starting through npm mirrors the supported development command
                # and lets Vite resolve its config/plugins from the frontend root.
                $frontendProcess = Start-Process -FilePath $prerequisites.NpmPath `
                    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$($script:FrontendPort)", "--strictPort") `
                    -WorkingDirectory (Join-Path $script:ProjectRoot "frontend") `
                    -RedirectStandardOutput $frontendOut `
                    -RedirectStandardError $frontendErr `
                    -WindowStyle Hidden `
                    -PassThru
            }
            finally {
                if ($null -eq $oldViteApiBaseUrl) {
                    Remove-Item Env:\VITE_API_BASE_URL -ErrorAction SilentlyContinue
                }
                else {
                    $env:VITE_API_BASE_URL = $oldViteApiBaseUrl
                }
            }
            Start-Sleep -Milliseconds 400
            if ($frontendProcess.HasExited) {
                throw "Frontend exited during startup. See '$frontendErr'."
            }
            $state.Frontend = New-ProcessEntry `
                -Process $frontendProcess `
                -Role "Frontend" `
                -Executable $frontendProcess.Path `
                -CommandToken "npm.cmd" `
                -StandardOutputLog $frontendOut `
                -StandardErrorLog $frontendErr
            Save-LauncherState -State $state
            $startedFrontend = $true
            Write-Host ("[OK] Frontend started (PID {0})." -f $frontendProcess.Id) -ForegroundColor Green
            Write-ControllerEvent "INFO" "Frontend started (PID $($frontendProcess.Id))."
        }
        else {
            Write-Host ("[OK] Frontend is already running (PID {0})." -f $frontendProcess.Id) -ForegroundColor Green
        }

        if (-not (Wait-ForUrl -Url "http://127.0.0.1:$($script:FrontendPort)" -Attempts 40)) {
            throw "Frontend health check failed. Review the frontend logs."
        }

        Write-Host ""
        Write-Host "Stone Crusher ERP is ready: http://localhost:5173" -ForegroundColor Green
        Write-Host "API documentation:            http://localhost:8000/docs"
        if (-not $NoBrowser) {
            Start-Process "http://localhost:$($script:FrontendPort)"
        }
    }
    catch {
        if ($startedFrontend -and $state.Frontend) {
            $null = Stop-VerifiedProcessTree -Entry $state.Frontend -Role "Frontend"
            $state.Frontend = $null
        }
        if ($startedBackend -and $state.Backend) {
            $null = Stop-VerifiedProcessTree -Entry $state.Backend -Role "Backend"
            $state.Backend = $null
        }
        Save-LauncherState -State $state
        Write-ControllerEvent "ERROR" ("Start failed: {0}" -f $_.Exception.Message)
        throw
    }
}

function Stop-StoneCrusher {
    Write-Heading "STOP STONE CRUSHER ERP"
    $state = Get-LauncherState
    $stoppedCount = 0
    $skippedCount = 0

    if ($state.Frontend) {
        if (Stop-VerifiedProcessTree -Entry $state.Frontend -Role "Frontend") {
            $stoppedCount++
        }
        else {
            $skippedCount++
        }
        $state.Frontend = $null
    }
    else {
        Write-Host "[INFO] No launcher-managed frontend is recorded."
    }

    if ($state.Backend) {
        if (Stop-VerifiedProcessTree -Entry $state.Backend -Role "Backend") {
            $stoppedCount++
        }
        else {
            $skippedCount++
        }
        $state.Backend = $null
    }
    else {
        Write-Host "[INFO] No launcher-managed backend is recorded."
    }

    Save-LauncherState -State $state
    Write-Host ""
    Write-Host ("Stop finished: {0} verified process(es) stopped, {1} unverified record(s) skipped." -f $stoppedCount, $skippedCount) -ForegroundColor Green
    Write-Host "MySQL was intentionally left running because other applications may use it."
}

function Show-StoneCrusherStatus {
    Write-Heading "STONE CRUSHER ERP STATUS"
    $state = Get-LauncherState
    $backend = Get-VerifiedManagedProcess -Entry $state.Backend -Role "Backend" -Quiet
    $frontend = Get-VerifiedManagedProcess -Entry $state.Frontend -Role "Frontend" -Quiet

    if ($backend) {
        Write-Host ("Backend:  RUNNING (launcher-managed PID {0})" -f $backend.Id) -ForegroundColor Green
    }
    else {
        $backendOwner = Get-ListeningProcessId -Port $script:BackendPort
        if ($backendOwner) {
            Write-Host ("Backend:  port {0} is used by untracked PID {1}" -f $script:BackendPort, $backendOwner) -ForegroundColor Yellow
        }
        else {
            Write-Host "Backend:  STOPPED" -ForegroundColor DarkGray
        }
    }

    if ($frontend) {
        Write-Host ("Frontend: RUNNING (launcher-managed PID {0})" -f $frontend.Id) -ForegroundColor Green
    }
    else {
        $frontendOwner = Get-ListeningProcessId -Port $script:FrontendPort
        if ($frontendOwner) {
            Write-Host ("Frontend: port {0} is used by untracked PID {1}" -f $script:FrontendPort, $frontendOwner) -ForegroundColor Yellow
        }
        else {
            Write-Host "Frontend: STOPPED" -ForegroundColor DarkGray
        }
    }

    try {
        $mysqlConfiguration = Assert-MySqlConfiguration
        if (Test-TcpPort -HostName $mysqlConfiguration.HostName -Port $mysqlConfiguration.Port -TimeoutMilliseconds 1200) {
            Write-Host ("Database: MYSQL available at {0}:{1}" -f $mysqlConfiguration.HostName, $mysqlConfiguration.Port) -ForegroundColor Green
        }
        else {
            Write-Host ("Database: MYSQL configured but not reachable at {0}:{1}" -f $mysqlConfiguration.HostName, $mysqlConfiguration.Port) -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host ("Database: configuration error - {0}" -f $_.Exception.Message) -ForegroundColor Red
    }

    Write-Host ("Logs:     {0}" -f $script:LogsRoot)
}

function Open-StoneCrusher {
    $frontendOwner = Get-ListeningProcessId -Port $script:FrontendPort
    if (-not $frontendOwner) {
        throw "The frontend is not running. Start Stone Crusher ERP first."
    }
    Start-Process "http://localhost:$($script:FrontendPort)"
}

function Open-StoneCrusherLogs {
    Initialize-Runtime
    Start-Process -FilePath "explorer.exe" -ArgumentList @($script:LogsRoot)
}

function Install-StoneCrusherShortcuts {
    Write-Heading "INSTALL DESKTOP SHORTCUTS"
    $shell = New-Object -ComObject WScript.Shell
    $desktop = $shell.SpecialFolders.Item("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        throw "Windows Desktop folder could not be located."
    }

    $shortcutDefinitions = @(
        @{
            Name = "Stone Crusher - Start.lnk"
            Target = Join-Path $script:ProjectRoot "Start Stone Crusher.cmd"
            Description = "Start Stone Crusher ERP"
            IconIndex = 137
        },
        @{
            Name = "Stone Crusher - Stop.lnk"
            Target = Join-Path $script:ProjectRoot "Stop Stone Crusher.cmd"
            Description = "Stop Stone Crusher ERP safely"
            IconIndex = 131
        },
        @{
            Name = "Stone Crusher - Control.lnk"
            Target = Join-Path $script:ProjectRoot "Stone Crusher Control.cmd"
            Description = "Open Stone Crusher ERP controls"
            IconIndex = 21
        }
    )

    foreach ($definition in $shortcutDefinitions) {
        if (-not (Test-Path -LiteralPath $definition.Target -PathType Leaf)) {
            throw "Launcher file '$($definition.Target)' is missing."
        }
        $shortcutPath = Join-Path $desktop $definition.Name
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $definition.Target
        $shortcut.WorkingDirectory = $script:ProjectRoot
        $shortcut.Description = $definition.Description
        $shortcut.IconLocation = "{0}\System32\shell32.dll,{1}" -f $env:SystemRoot, $definition.IconIndex
        $shortcut.Save()
        Write-Host ("[OK] {0}" -f $shortcutPath) -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Desktop shortcuts are ready. Keep the project folder in its current location."
}

function Invoke-Safely {
    param([Parameter(Mandatory)][scriptblock]$Operation)

    try {
        & $Operation
    }
    catch {
        Write-Host ""
        Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-ControllerEvent "ERROR" $_.Exception.Message
    }
}

function Show-ControlMenu {
    while ($true) {
        Write-Heading "STONE CRUSHER ERP CONTROL"
        Write-Host "  1. Start project"
        Write-Host "  2. Stop project"
        Write-Host "  3. Show status"
        Write-Host "  4. Open application"
        Write-Host "  5. Open logs"
        Write-Host "  6. Create Desktop shortcuts"
        Write-Host "  0. Exit"
        Write-Host ""
        $selection = Read-Host "Choose an option"

        switch ($selection) {
            "1" { Invoke-Safely { Start-StoneCrusher }; Read-Host "Press Enter to continue" | Out-Null }
            "2" { Invoke-Safely { Stop-StoneCrusher }; Read-Host "Press Enter to continue" | Out-Null }
            "3" { Invoke-Safely { Show-StoneCrusherStatus }; Read-Host "Press Enter to continue" | Out-Null }
            "4" { Invoke-Safely { Open-StoneCrusher } }
            "5" { Invoke-Safely { Open-StoneCrusherLogs } }
            "6" { Invoke-Safely { Install-StoneCrusherShortcuts }; Read-Host "Press Enter to continue" | Out-Null }
            "0" { return }
            default {
                Write-Host "Please choose a number from 0 to 6." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
            }
        }
    }
}

try {
    switch ($Action) {
        "Start" { Start-StoneCrusher }
        "Stop" { Stop-StoneCrusher }
        "Status" { Show-StoneCrusherStatus }
        "Open" { Open-StoneCrusher }
        "Logs" { Open-StoneCrusherLogs }
        "InstallShortcuts" { Install-StoneCrusherShortcuts }
        default { Show-ControlMenu }
    }
}
catch {
    Write-Host ""
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-ControllerEvent "ERROR" $_.Exception.Message
    exit 1
}
