#requires -Version 5.1

<#
.SYNOPSIS
Prepares Stone Crusher ERP on a Windows PC with MySQL 8.

.DESCRIPTION
Checks Python, Node.js, npm, the MySQL command-line client and the local MySQL
port. When MySQL is missing, it can install the official MySQL Community Server
package (server and required Configurator only, without Workbench) through
Windows Package Manager. It can then create a dedicated MySQL database/user
after explicit approval, create an isolated Python virtual environment, install
backend/frontend dependencies, create a safe .env file, and apply Alembic
migrations.

MySQL installation and database provisioning both require confirmation. This
script does not silently replace an existing .env file.

.PARAMETER CheckOnly
Only check prerequisites. No files, dependencies, databases, or services change.

.PARAMETER ConfigureDatabase
Explicitly create/update the dedicated MySQL database and application user.
The MySQL administrator, application database, and first-login passwords are
requested securely and are never placed in command-line arguments.

.PARAMETER InstallMySqlServer
Install MySQL Community Server through winget when mysql.exe is not present.
Without this switch, interactive setup asks before installing it.

.PARAMETER ForceEnvironment
Allow creation of a new .env when one already exists. The original is copied to
a timestamped backup first. This switch requires ConfigureDatabase.

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup\setup-windows.ps1 -CheckOnly

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup\setup-windows.ps1 -ConfigureDatabase

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup\setup-windows.ps1 -InstallMySqlServer -ConfigureDatabase
#>

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$ConfigureDatabase,
    [switch]$InstallMySqlServer,
    [switch]$ForceEnvironment,
    [switch]$SkipBackendDependencies,
    [switch]$SkipFrontendDependencies,
    [switch]$SkipMigrations,
    [ValidatePattern("^[A-Za-z0-9_.-]+$")]
    [string]$MySqlHost = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$MySqlPort = 3306,
    [ValidatePattern("^[A-Za-z0-9_]+$")]
    [string]$DatabaseName = "stone_creysher",
    [ValidatePattern("^[A-Za-z0-9_]+$")]
    [string]$DatabaseUser = "stone_app",
    [ValidatePattern("^[A-Za-z0-9_]+$")]
    [string]$MySqlAdminUser = "root",
    [ValidatePattern("^[A-Za-z0-9_.-]+$")]
    [string]$FirstAdminUsername = "admin"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path -Path $PSScriptRoot -ChildPath "..\..")
)
$BackendDirectory = Join-Path -Path $ProjectRoot -ChildPath "backend"
$FrontendDirectory = Join-Path -Path $ProjectRoot -ChildPath "frontend"
$EnvironmentExamplePath = Join-Path -Path $ProjectRoot -ChildPath ".env.example"
$EnvironmentPath = Join-Path -Path $ProjectRoot -ChildPath ".env"
$VirtualEnvironmentPath = Join-Path -Path $BackendDirectory -ChildPath "venv"
$VirtualEnvironmentPython = Join-Path -Path $VirtualEnvironmentPath -ChildPath "Scripts\python.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("==> {0}" -f $Message) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host ("[OK] {0}" -f $Message) -ForegroundColor Green
}

function Write-Notice {
    param([string]$Message)
    Write-Host ("[INFO] {0}" -f $Message) -ForegroundColor DarkCyan
}

function Write-WarningMessage {
    param([string]$Message)
    Write-Host ("[WARNING] {0}" -f $Message) -ForegroundColor Yellow
}

function Get-RequiredCommand {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    $command = Get-Command -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw ("{0} was not found. {1}" -f $Name, $InstallHint)
    }
    return $command.Source
}

function Assert-MinimumVersion {
    param(
        [string]$Name,
        [string]$VersionText,
        [version]$Minimum
    )

    $match = [regex]::Match($VersionText, "(\d+)\.(\d+)(?:\.(\d+))?")
    if (-not $match.Success) {
        throw ("Could not determine the {0} version from: {1}" -f $Name, $VersionText.Trim())
    }

    $patch = 0
    if ($match.Groups[3].Success) {
        $patch = [int]$match.Groups[3].Value
    }
    $actual = [version]::new(
        [int]$match.Groups[1].Value,
        [int]$match.Groups[2].Value,
        $patch
    )
    if ($actual -lt $Minimum) {
        throw ("{0} {1} or newer is required; found {2}." -f $Name, $Minimum, $actual)
    }
    Write-Success ("{0} {1}" -f $Name, $actual)
}

function Find-MySqlClient {
    $command = Get-Command -Name "mysql.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:ProgramFiles) {
        $candidates.Add(
            (Join-Path $env:ProgramFiles "MySQL\MySQL Server 8.4\bin\mysql.exe")
        )
        $candidates.Add(
            (Join-Path $env:ProgramFiles "MySQL\MySQL Server 8.0\bin\mysql.exe")
        )
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add(
            (Join-Path ${env:ProgramFiles(x86)} "MySQL\MySQL Server 8.0\bin\mysql.exe")
        )
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Install-MySqlCommunityServer {
    $wingetExecutable = Get-RequiredCommand -Name "winget.exe" `
        -InstallHint "Install or update Microsoft App Installer, then rerun setup."

    Write-Step "Installing MySQL Community Server"
    Write-Notice (
        "This installs Oracle MySQL Community Server and its required Configurator only; " +
        "MySQL Workbench is not installed."
    )
    Write-Notice (
        "Complete MySQL Configurator using port {0}, create a root password, and configure " +
        "MySQL as an automatically started Windows service." -f $MySqlPort
    )
    Invoke-CheckedCommand -Description "MySQL Community Server installation" -Command {
        & $wingetExecutable install `
            --id Oracle.MySQL `
            --exact `
            --source winget `
            --interactive `
            --accept-package-agreements `
            --accept-source-agreements
    }
    Read-Host (
        "Finish MySQL Configurator and ensure its Windows service is running, " +
        "then press Enter to continue"
    ) | Out-Null
}

function Test-TcpPort {
    param(
        [string]$ComputerName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 1500
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect($ComputerName, $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Read-ConfirmedSecret {
    param(
        [string]$Prompt,
        [int]$MinimumLength = 8
    )

    while ($true) {
        $first = Read-Host -Prompt $Prompt -AsSecureString
        $second = Read-Host -Prompt "Confirm the value" -AsSecureString
        $firstText = ConvertFrom-SecureValue -Value $first
        $secondText = ConvertFrom-SecureValue -Value $second
        if ($firstText.Length -lt $MinimumLength) {
            Write-WarningMessage ("Use at least {0} characters." -f $MinimumLength)
            continue
        }
        if ($firstText -ne $secondText) {
            Write-WarningMessage "The values did not match. Try again."
            continue
        }
        return $first
    }
}

function ConvertFrom-SecureValue {
    param([Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function ConvertTo-MySqlString {
    param([string]$Value)
    return $Value.Replace('\', '\\').Replace("'", "''")
}

function ConvertTo-DotEnvString {
    param([string]$Value)
    return '"' + $Value.Replace('\', '\\').Replace('"', '\"') + '"'
}

function New-RandomSecret {
    $bytes = New-Object byte[] 48
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Set-DotEnvValue {
    param(
        [string]$Content,
        [string]$Key,
        [string]$Value
    )

    $pattern = "(?m)^" + [regex]::Escape($Key) + "=.*$"
    $line = $Key + "=" + $Value
    if ([regex]::IsMatch($Content, $pattern)) {
        return [regex]::Replace($Content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{
            param($match)
            return $line
        })
    }
    return $Content.TrimEnd() + [Environment]::NewLine + $line + [Environment]::NewLine
}

function Invoke-CheckedCommand {
    param(
        [string]$Description,
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw ("{0} failed with exit code {1}." -f $Description, $LASTEXITCODE)
    }
}

Write-Host "Stone Crusher ERP - Windows setup" -ForegroundColor White
Write-Notice ("Project folder: {0}" -f $ProjectRoot)

if (-not (Test-Path -LiteralPath $BackendDirectory -PathType Container) -or
    -not (Test-Path -LiteralPath $FrontendDirectory -PathType Container) -or
    -not (Test-Path -LiteralPath $EnvironmentExamplePath -PathType Leaf)) {
    throw "Run this script from a complete project copy. Required backend, frontend, or .env.example files are missing."
}

if ($ForceEnvironment -and -not $ConfigureDatabase) {
    throw "-ForceEnvironment is only allowed together with -ConfigureDatabase."
}

Write-Step "Checking required software"

$basePythonExecutable = $null
$basePythonPrefix = @()
$pythonVersionText = ""

$pythonCommand = Get-Command -Name "python.exe" -ErrorAction SilentlyContinue
if ($null -ne $pythonCommand) {
    $candidateVersion = (& $pythonCommand.Source --version 2>$null | Out-String)
    if ($LASTEXITCODE -eq 0) {
        $basePythonExecutable = $pythonCommand.Source
        $pythonVersionText = $candidateVersion
    }
}

if ($null -eq $basePythonExecutable) {
    $pythonLauncher = Get-Command -Name "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pythonLauncher) {
        $candidateVersion = (& $pythonLauncher.Source -3 --version 2>$null | Out-String)
        if ($LASTEXITCODE -eq 0) {
            $basePythonExecutable = $pythonLauncher.Source
            $basePythonPrefix = @("-3")
            $pythonVersionText = $candidateVersion
        }
    }
}

if ($null -eq $basePythonExecutable) {
    throw "A working Python installation was not found. Install 64-bit Python 3.10 or newer and enable Add Python to PATH."
}
Assert-MinimumVersion -Name "Python" -VersionText $pythonVersionText -Minimum ([version]"3.10.0")

$nodeExecutable = Get-RequiredCommand -Name "node.exe" `
    -InstallHint "Install the Node.js LTS release (18 or newer)."
$npmExecutable = Get-RequiredCommand -Name "npm.cmd" `
    -InstallHint "Reinstall Node.js and include npm."
$nodeVersionText = (& $nodeExecutable --version 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw "Node.js was found but could not be started."
}
Assert-MinimumVersion -Name "Node.js" -VersionText $nodeVersionText -Minimum ([version]"18.0.0")
$npmVersionText = (& $npmExecutable --version 2>&1 | Out-String).Trim()
Write-Success ("npm {0}" -f $npmVersionText)

$mysqlExecutable = Find-MySqlClient
if ($null -eq $mysqlExecutable) {
    if ($CheckOnly) {
        throw (
            "mysql.exe was not found. No changes were made. Run Setup New Computer.cmd " +
            "to install MySQL Community Server, or install MySQL 8.0 or newer manually."
        )
    }

    $installMySqlNow = [bool]$InstallMySqlServer
    if (-not $installMySqlNow) {
        $answer = Read-Host (
            "MySQL is not installed. Install MySQL Community Server only " +
            "(no Workbench) now? [Y/n]"
        )
        $installMySqlNow = [string]::IsNullOrWhiteSpace($answer) -or
            $answer.Trim().ToLowerInvariant() -eq "y" -or
            $answer.Trim().ToLowerInvariant() -eq "yes"
    }
    if (-not $installMySqlNow) {
        throw (
            "MySQL Server is required. Install MySQL 8.0 or newer with Client Programs, " +
            "or rerun with -InstallMySqlServer."
        )
    }

    Install-MySqlCommunityServer
    $mysqlExecutable = Find-MySqlClient
    if ($null -eq $mysqlExecutable) {
        throw (
            "MySQL installation finished, but mysql.exe was not found. Complete MySQL " +
            "Configurator and confirm the server bin folder exists, then rerun setup."
        )
    }
}
$mysqlVersionText = (& $mysqlExecutable --version 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw "The MySQL client was found but could not be started."
}
Assert-MinimumVersion -Name "MySQL client" -VersionText $mysqlVersionText -Minimum ([version]"8.0.0")

$mysqlServices = @(
    Get-Service -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match "^MySQL" -or $_.DisplayName -match "^MySQL"
        }
)
if ($mysqlServices.Count -gt 0) {
    foreach ($service in $mysqlServices) {
        if ($service.Status -eq "Running") {
            Write-Success ("Windows service {0} is running" -f $service.Name)
        }
        else {
            Write-WarningMessage (
                "Windows service {0} is {1}. Start it manually before setup." -f
                $service.Name,
                $service.Status
            )
        }
    }
}
else {
    Write-WarningMessage "No MySQL Windows service was detected. A remote or custom MySQL service can still be used."
}

$mysqlPortAvailable = Test-TcpPort -ComputerName $MySqlHost -Port $MySqlPort
if ($mysqlPortAvailable) {
    Write-Success ("MySQL is accepting TCP connections at {0}:{1}" -f $MySqlHost, $MySqlPort)
}
else {
    Write-WarningMessage ("Nothing answered at {0}:{1}. The MySQL service may be stopped." -f $MySqlHost, $MySqlPort)
}

if ($CheckOnly) {
    Write-Host ""
    Write-Success "Prerequisite check finished. No files, databases, packages, or services were changed."
    exit 0
}

$configureDatabaseNow = [bool]$ConfigureDatabase
if (-not (Test-Path -LiteralPath $EnvironmentPath -PathType Leaf) -and
    -not $configureDatabaseNow) {
    $answer = Read-Host "No .env file exists. Configure a new local MySQL database now? [Y/n]"
    $configureDatabaseNow = [string]::IsNullOrWhiteSpace($answer) -or
        $answer.Trim().ToLowerInvariant() -eq "y" -or
        $answer.Trim().ToLowerInvariant() -eq "yes"
    if (-not $configureDatabaseNow) {
        throw "Setup stopped without changes. Configure MySQL and .env manually, or rerun with -ConfigureDatabase."
    }
}

if ($configureDatabaseNow) {
    if ((Test-Path -LiteralPath $EnvironmentPath -PathType Leaf) -and
        -not $ForceEnvironment) {
        throw "An existing .env was found. It was not changed. To deliberately rebuild it, rerun with -ConfigureDatabase -ForceEnvironment; a backup will be created."
    }
    if (-not $mysqlPortAvailable) {
        throw "MySQL is not reachable. Start the installed MySQL service manually and rerun this script."
    }

    Write-Step "Collecting private values"
    Write-Notice "Passwords are requested in hidden prompts and are not passed on command lines."
    $databasePasswordSecure = Read-ConfirmedSecret `
        -Prompt ("Password for MySQL application user '{0}'" -f $DatabaseUser) `
        -MinimumLength 10
    $mysqlAdminPasswordSecure = Read-Host `
        -Prompt ("Existing password for MySQL administrator '{0}'" -f $MySqlAdminUser) `
        -AsSecureString
    $firstAdminPasswordSecure = Read-ConfirmedSecret `
        -Prompt ("First login password for ERP user '{0}'" -f $FirstAdminUsername) `
        -MinimumLength 8

    $databasePassword = ConvertFrom-SecureValue -Value $databasePasswordSecure
    $mysqlAdminPassword = ConvertFrom-SecureValue -Value $mysqlAdminPasswordSecure
    $firstAdminPassword = ConvertFrom-SecureValue -Value $firstAdminPasswordSecure

    Write-Step "Creating the dedicated MySQL database and user"
    $escapedDatabasePassword = ConvertTo-MySqlString -Value $databasePassword
    $sqlLines = New-Object System.Collections.Generic.List[string]
    $sqlLines.Add(
        ("CREATE DATABASE IF NOT EXISTS ``{0}`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" -f $DatabaseName)
    )
    foreach ($grantHost in @("localhost", "127.0.0.1")) {
        $sqlLines.Add(
            ("CREATE USER IF NOT EXISTS '{0}'@'{1}' IDENTIFIED BY '{2}';" -f
                $DatabaseUser,
                $grantHost,
                $escapedDatabasePassword)
        )
        $sqlLines.Add(
            ("ALTER USER '{0}'@'{1}' IDENTIFIED BY '{2}';" -f
                $DatabaseUser,
                $grantHost,
                $escapedDatabasePassword)
        )
        $sqlLines.Add(
            ("GRANT ALL PRIVILEGES ON ``{0}``.* TO '{1}'@'{2}';" -f
                $DatabaseName,
                $DatabaseUser,
                $grantHost)
        )
    }
    $sqlLines.Add("FLUSH PRIVILEGES;")

    $temporarySqlPath = Join-Path `
        -Path ([System.IO.Path]::GetTempPath()) `
        -ChildPath ("stone-setup-{0}.sql" -f [guid]::NewGuid().ToString("N"))
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $temporarySqlPath,
        ($sqlLines -join [Environment]::NewLine),
        $utf8WithoutBom
    )
    $mysqlSourcePath = $temporarySqlPath.Replace('\', '/')
    $previousMySqlPassword = $env:MYSQL_PWD
    $hadPreviousMySqlPassword = Test-Path Env:\MYSQL_PWD
    try {
        $env:MYSQL_PWD = $mysqlAdminPassword
        & $mysqlExecutable `
            --protocol=TCP `
            ("--host={0}" -f $MySqlHost) `
            ("--port={0}" -f $MySqlPort) `
            ("--user={0}" -f $MySqlAdminUser) `
            --default-character-set=utf8mb4 `
            ("--execute=source {0}" -f $mysqlSourcePath)
        if ($LASTEXITCODE -ne 0) {
            throw "MySQL rejected the database provisioning command. Verify the administrator password and permissions."
        }

        $env:MYSQL_PWD = $databasePassword
        & $mysqlExecutable `
            --protocol=TCP `
            ("--host={0}" -f $MySqlHost) `
            ("--port={0}" -f $MySqlPort) `
            ("--user={0}" -f $DatabaseUser) `
            ("--database={0}" -f $DatabaseName) `
            --batch `
            --silent `
            "--execute=SELECT 1;"
        if ($LASTEXITCODE -ne 0) {
            throw "The new application user could not connect to the database."
        }
    }
    finally {
        if ($hadPreviousMySqlPassword) {
            $env:MYSQL_PWD = $previousMySqlPassword
        }
        else {
            Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $temporarySqlPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporarySqlPath -Force
        }
    }
    Write-Success ("MySQL database '{0}' and application user '{1}' are ready" -f $DatabaseName, $DatabaseUser)

    Write-Step "Creating the environment file"
    if (Test-Path -LiteralPath $EnvironmentPath -PathType Leaf) {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupDirectory = Join-Path `
            -Path $env:LOCALAPPDATA `
            -ChildPath "StoneCrusherERP\environment-backups"
        if (-not (Test-Path -LiteralPath $backupDirectory -PathType Container)) {
            New-Item -Path $backupDirectory -ItemType Directory -Force | Out-Null
        }
        $backupPath = Join-Path `
            -Path $backupDirectory `
            -ChildPath (".env.backup-{0}" -f $timestamp)
        Copy-Item -LiteralPath $EnvironmentPath -Destination $backupPath
        Write-Notice ("Existing .env copied to {0}" -f $backupPath)
    }

    $environmentContent = Get-Content -LiteralPath $EnvironmentExamplePath -Raw
    $encodedDatabaseUser = [uri]::EscapeDataString($DatabaseUser)
    $encodedDatabasePassword = [uri]::EscapeDataString($databasePassword)
    $databaseUrl = "mysql+pymysql://{0}:{1}@{2}:{3}/{4}?charset=utf8mb4" -f `
        $encodedDatabaseUser,
        $encodedDatabasePassword,
        $MySqlHost,
        $MySqlPort,
        $DatabaseName

    $environmentContent = Set-DotEnvValue $environmentContent "SECRET_KEY" (New-RandomSecret)
    $environmentContent = Set-DotEnvValue $environmentContent "MYSQL_USER" $DatabaseUser
    $environmentContent = Set-DotEnvValue $environmentContent "MYSQL_PASSWORD" (ConvertTo-DotEnvString $databasePassword)
    $environmentContent = Set-DotEnvValue $environmentContent "MYSQL_DATABASE" $DatabaseName
    $environmentContent = Set-DotEnvValue $environmentContent "MYSQL_HOST" $MySqlHost
    $environmentContent = Set-DotEnvValue $environmentContent "MYSQL_PORT" ([string]$MySqlPort)
    $environmentContent = Set-DotEnvValue $environmentContent "DATABASE_URL" $databaseUrl
    $environmentContent = Set-DotEnvValue $environmentContent "FIRST_ADMIN_USERNAME" $FirstAdminUsername
    $environmentContent = Set-DotEnvValue $environmentContent "FIRST_ADMIN_PASSWORD" (ConvertTo-DotEnvString $firstAdminPassword)

    [System.IO.File]::WriteAllText(
        $EnvironmentPath,
        $environmentContent,
        $utf8WithoutBom
    )
    Write-Success ".env created with a random application secret and URL-encoded database password"
}
else {
    Write-Notice "Existing .env preserved. Database provisioning was not requested."
}

Write-Step "Preparing the Python backend"
if (-not (Test-Path -LiteralPath $VirtualEnvironmentPython -PathType Leaf)) {
    & $basePythonExecutable @basePythonPrefix -m venv $VirtualEnvironmentPath
    if ($LASTEXITCODE -ne 0) {
        throw "Python virtual-environment creation failed."
    }
    Write-Success ("Virtual environment created at {0}" -f $VirtualEnvironmentPath)
}
else {
    Write-Notice "Existing backend virtual environment will be reused."
}

if (-not $SkipBackendDependencies) {
    Invoke-CheckedCommand -Description "pip upgrade" -Command {
        & $VirtualEnvironmentPython -m pip install --upgrade pip
    }
    Invoke-CheckedCommand -Description "backend dependency installation" -Command {
        & $VirtualEnvironmentPython -m pip install -r (Join-Path $BackendDirectory "requirements.txt")
    }
    Write-Success "Backend dependencies installed"
}
else {
    Write-Notice "Backend dependency installation skipped by request."
}

Write-Step "Preparing the React frontend"
if (-not $SkipFrontendDependencies) {
    Push-Location $FrontendDirectory
    try {
        Invoke-CheckedCommand -Description "frontend dependency installation" -Command {
            & $npmExecutable ci
        }
    }
    finally {
        Pop-Location
    }
    Write-Success "Frontend dependencies installed from package-lock.json"
}
else {
    Write-Notice "Frontend dependency installation skipped by request."
}

if (-not $SkipMigrations) {
    Write-Step "Applying MySQL schema migrations"
    Push-Location $BackendDirectory
    try {
        Invoke-CheckedCommand -Description "Alembic migration" -Command {
            & $VirtualEnvironmentPython -m alembic upgrade head
        }
    }
    finally {
        Pop-Location
    }
    Write-Success "Database schema is at the latest Alembic revision"
}
else {
    Write-WarningMessage "Database migrations were skipped. Run them before starting the API."
}

Write-Host ""
Write-Host "Setup completed." -ForegroundColor Green
Write-Host ""
Write-Host "Start the API in PowerShell window 1:"
Write-Host ('  Set-Location "{0}"' -f $BackendDirectory)
Write-Host "  .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Write-Host ""
Write-Host "Start the web interface in PowerShell window 2:"
Write-Host ('  Set-Location "{0}"' -f $FrontendDirectory)
Write-Host "  npm.cmd run dev"
Write-Host ""
Write-Host "Then open http://localhost:5173 and sign in with the first administrator credentials you configured."
Write-Host "Use the gear icon in the top-right corner to enter the real shop, GST, address, and bank details."
