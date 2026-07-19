param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$resolvedBackup = [System.IO.Path]::GetFullPath($BackupPath)
if (-not (Test-Path -LiteralPath $resolvedBackup -PathType Leaf)) {
    throw "Backup file not found: $resolvedBackup"
}
if (-not $Force) {
    throw "Restore replaces data in the configured database. Re-run with -Force after verifying the backup and target."
}

Get-Content -LiteralPath $resolvedBackup -Encoding Byte -ReadCount 0 |
    & docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
if ($LASTEXITCODE -ne 0) {
    throw "Postgres restore failed. Inspect the target database and backup file."
}
Write-Host "Restore completed from $resolvedBackup"
