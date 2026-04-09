param(
    [string]$NewPassword,
    [string]$ServiceName = "postgresql-x64-18",
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin",
    [string]$DataDir = "C:\Program Files\PostgreSQL\18\data"
)

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    throw "Run this script from PowerShell opened as Administrator."
}

if (-not $NewPassword) {
    $securePassword = Read-Host "Enter the new postgres password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $NewPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not $NewPassword) {
    throw "A new postgres password is required."
}

$pgHba = Join-Path $DataDir "pg_hba.conf"
$psql = Join-Path $PgBin "psql.exe"
$backup = Join-Path $DataDir ("pg_hba.conf.codex-backup-" + (Get-Date -Format "yyyyMMddHHmmss"))

if (-not (Test-Path -LiteralPath $pgHba)) {
    throw "pg_hba.conf was not found at $pgHba"
}

if (-not (Test-Path -LiteralPath $psql)) {
    throw "psql.exe was not found at $psql"
}

Copy-Item -LiteralPath $pgHba -Destination $backup -Force

try {
    $lines = Get-Content -LiteralPath $pgHba
    $updated = foreach ($line in $lines) {
        if (
            $line -match "^\s*host\s+all\s+all\s+127\.0\.0\.1/32\s+\S+" -or
            $line -match "^\s*host\s+all\s+all\s+::1/128\s+\S+" -or
            $line -match "^\s*local\s+all\s+all\s+\S+"
        ) {
            $line -replace "\S+\s*$", "trust"
        }
        else {
            $line
        }
    }
    Set-Content -LiteralPath $pgHba -Value $updated -Encoding ascii

    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 3

    $escapedPassword = $NewPassword -replace "'", "''"
    & $psql -w -h 127.0.0.1 -p 5432 -U postgres -d postgres -v "ON_ERROR_STOP=1" -c "ALTER USER postgres WITH PASSWORD '$escapedPassword';" | Out-Null

    Copy-Item -LiteralPath $backup -Destination $pgHba -Force
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 3

    $env:PGPASSWORD = $NewPassword
    & $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v "ON_ERROR_STOP=1" -c "SELECT current_user;"
    $env:PGPASSWORD = $null

    Write-Host "PostgreSQL postgres password reset and verified."
    Write-Host "Backup kept at $backup"
}
catch {
    Copy-Item -LiteralPath $backup -Destination $pgHba -Force
    try {
        Restart-Service -Name $ServiceName -Force
    }
    catch {
        Write-Warning "Restored pg_hba.conf, but PostgreSQL service restart failed. Restart it manually from Services."
    }
    throw
}
finally {
    $env:PGPASSWORD = $null
}
