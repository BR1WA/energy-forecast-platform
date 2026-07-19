param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$directory = Split-Path -Parent $resolvedOutput
if (-not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
if (Test-Path -LiteralPath $resolvedOutput) {
    throw "Refusing to overwrite existing backup: $resolvedOutput"
}

& docker compose exec -T db sh -c 'pg_dump --format=custom --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' > $resolvedOutput
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $resolvedOutput -Force -ErrorAction SilentlyContinue
    throw "Postgres backup failed."
}
Write-Host "Backup written to $resolvedOutput"
