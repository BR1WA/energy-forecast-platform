param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $resolvedOutput) {
    throw "Refusing to overwrite existing backup directory: $resolvedOutput"
}
New-Item -ItemType Directory -Path $resolvedOutput | Out-Null

$databaseBackup = Join-Path $resolvedOutput 'database.dump'
$avatarBackup = Join-Path $resolvedOutput 'avatars.tar.gz'
try {
    & docker compose exec -T db sh -c 'rm -f /tmp/product-v1.dump && pg_dump --format=custom --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --file=/tmp/product-v1.dump'
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL backup failed.' }
    & docker compose cp db:/tmp/product-v1.dump $databaseBackup
    if ($LASTEXITCODE -ne 0) { throw 'Unable to copy PostgreSQL backup from the database container.' }

    & docker compose exec -T backend sh -c 'rm -f /tmp/product-v1-avatars.tar.gz && tar -C /app/static/avatars -czf /tmp/product-v1-avatars.tar.gz .'
    if ($LASTEXITCODE -ne 0) { throw 'Avatar backup failed.' }
    & docker compose cp backend:/tmp/product-v1-avatars.tar.gz $avatarBackup
    if ($LASTEXITCODE -ne 0) { throw 'Unable to copy avatar backup from the backend container.' }

    $manifest = [ordered]@{
        schema_version = 1
        created_at_utc = [DateTime]::UtcNow.ToString('o')
        database_file = 'database.dump'
        database_sha256 = (Get-FileHash -LiteralPath $databaseBackup -Algorithm SHA256).Hash.ToLowerInvariant()
        avatars_file = 'avatars.tar.gz'
        avatars_sha256 = (Get-FileHash -LiteralPath $avatarBackup -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resolvedOutput 'manifest.json') -Encoding UTF8
}
catch {
    Remove-Item -LiteralPath $resolvedOutput -Recurse -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    & docker compose exec -T db rm -f /tmp/product-v1.dump 2>$null
    & docker compose exec -T backend rm -f /tmp/product-v1-avatars.tar.gz 2>$null
}

Write-Host "Product backup written to $resolvedOutput"
