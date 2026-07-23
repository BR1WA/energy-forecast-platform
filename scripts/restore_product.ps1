param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$resolvedBackup = [System.IO.Path]::GetFullPath($BackupDirectory)
$manifestPath = Join-Path $resolvedBackup 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Product backup manifest not found: $manifestPath"
}
if (-not $Force) {
    throw 'Restore replaces the configured database and avatar volume. Re-run with -Force only after stopping application writes and verifying the target.'
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$databaseBackup = Join-Path $resolvedBackup $manifest.database_file
$avatarBackup = Join-Path $resolvedBackup $manifest.avatars_file
foreach ($path in @($databaseBackup, $avatarBackup)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Backup member not found: $path" }
}
if ((Get-FileHash -LiteralPath $databaseBackup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.database_sha256) {
    throw 'Database backup checksum does not match the manifest.'
}
if ((Get-FileHash -LiteralPath $avatarBackup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.avatars_sha256) {
    throw 'Avatar backup checksum does not match the manifest.'
}

& docker compose cp $databaseBackup db:/tmp/product-v1-restore.dump
if ($LASTEXITCODE -ne 0) { throw 'Unable to copy database backup into the database container.' }
& docker compose cp $avatarBackup backend:/tmp/product-v1-avatars-restore.tar.gz
if ($LASTEXITCODE -ne 0) { throw 'Unable to copy avatar backup into the backend container.' }

try {
    & docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" /tmp/product-v1-restore.dump'
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL restore failed. The target requires operator inspection.' }
    & docker compose exec -T backend sh -c 'test "$(readlink -f /app/static/avatars)" = "/app/static/avatars" && find /app/static/avatars -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -C /app/static/avatars -xzf /tmp/product-v1-avatars-restore.tar.gz'
    if ($LASTEXITCODE -ne 0) { throw 'Avatar restore failed. The target requires operator inspection.' }
}
finally {
    & docker compose exec -T db rm -f /tmp/product-v1-restore.dump 2>$null
    & docker compose exec -T backend rm -f /tmp/product-v1-avatars-restore.tar.gz 2>$null
}

Write-Host 'Product database and avatar restore completed. Run the documented verification checklist before re-enabling writes.'
