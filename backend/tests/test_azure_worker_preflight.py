"""PowerShell preflight contract tests that never contact Azure."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "prepare_azure_defense_workers.ps1"
DIGEST_IMAGE = "example.azurecr.io/energyai/backend@sha256:" + "a" * 64


pytestmark = pytest.mark.skipif(
    POWERSHELL is None, reason="PowerShell is required for deployment preflight tests"
)


def run_powershell(body: str) -> None:
    command = f"""
$ErrorActionPreference = 'Stop'
function Assert-Throws([scriptblock]$Action) {{
    try {{ & $Action }} catch {{ return }}
    throw 'Expected command to throw.'
}}
. '{SCRIPT.as_posix()}' -BackendImage '{DIGEST_IMAGE}' -RevisionSuffix 'review' | Out-Null
{body}
"""
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


MOCK_APPLY_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$global:AzCalls = [System.Collections.Generic.List[object]]::new()
$global:MockRevisionConflict = $false
$global:MockReadFailure = ''
$global:MockMutationFailure = ''
$subscriptionId = '00000000-0000-0000-0000-000000000001'
$resourceGroup = 'rg-energyai-test'
$apiName = 'ca-energyai-api'
$emailName = 'ca-energyai-email-worker'
$simulationName = 'ca-energyai-simulation-worker'
$alertName = 'ca-energyai-alert-worker'
$digestImage = '__DIGEST_IMAGE__'

function Get-CallValue($Call, [string]$Option) {
    $index = [Array]::IndexOf([string[]]$Call, $Option)
    if ($index -lt 0 -or $index + 1 -ge $Call.Count) { return $null }
    return [string]$Call[$index + 1]
}

function Get-CallSection($Call, [string]$Start, [string]$End) {
    $startIndex = [Array]::IndexOf([string[]]$Call, $Start)
    $endIndex = [Array]::IndexOf([string[]]$Call, $End)
    if ($startIndex -lt 0 -or $endIndex -le $startIndex) { return @() }
    return @($Call[($startIndex + 1)..($endIndex - 1)])
}

function Test-AzWrite($Call) {
    return $Call[0] -eq 'containerapp' -and (
        $Call[1] -in @('create', 'update') -or
        ($Call[1] -eq 'secret' -and $Call[2] -eq 'set')
    )
}

function Assert-NoAzWrites {
    $writes = @($global:AzCalls | Where-Object { Test-AzWrite $_ })
    if ($writes.Count -ne 0) { throw "Expected zero Azure writes, observed $($writes.Count)." }
}

function Assert-ScriptFails([scriptblock]$Action, [string]$Pattern) {
    try { & $Action } catch {
        if ([string]$_.Exception.Message -notmatch $Pattern) {
            throw "Unexpected failure: $($_.Exception.Message)"
        }
        return
    }
    throw 'Expected deployment script to fail.'
}

function New-ApiApp {
    $environmentId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.App/managedEnvironments/cae-energyai"
    return [pscustomobject]@{
        id = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.App/containerApps/$apiName"
        name = $apiName
        location = 'westeurope'
        properties = [pscustomobject]@{
            managedEnvironmentId = $environmentId
            configuration = [pscustomobject]@{
                registries = @([pscustomobject]@{ server = 'example.azurecr.io'; username = 'registry-user'; passwordSecretRef = 'existing-registry-secret' })
            }
            template = [pscustomobject]@{
                containers = @([pscustomobject]@{
                    name = $apiName
                    image = 'example.azurecr.io/energyai/backend@sha256:' + ('b' * 64)
                    command = @('python')
                    args = @('-m', 'app.cli', 'serve')
                    env = @(
                        [pscustomobject]@{ name = 'DATABASE_URL'; secretRef = 'database-url' },
                        [pscustomobject]@{ name = 'JWT_SECRET_KEY'; secretRef = 'jwt-secret' },
                        [pscustomobject]@{ name = 'ADMIN_PASSWORD'; secretRef = 'admin-password' },
                        [pscustomobject]@{ name = 'LEGAL_OWNER_NAME'; value = 'EnergyAI' },
                        [pscustomobject]@{ name = 'LEGAL_CONTACT_EMAIL'; value = 'legal@example.test' },
                        [pscustomobject]@{ name = 'SUPPORT_EMAIL'; value = 'support@example.test' },
                        [pscustomobject]@{ name = 'LEGAL_EFFECTIVE_DATE'; value = '2026-01-01' },
                        [pscustomobject]@{ name = 'EMAIL_DELIVERY_ENABLED'; value = 'true' },
                        [pscustomobject]@{ name = 'SMTP_USERNAME'; secretRef = 'smtp-username' },
                        [pscustomobject]@{ name = 'SMTP_PASSWORD'; secretRef = 'smtp-password' },
                        [pscustomobject]@{ name = 'GOOGLE_AUTH_ENABLED'; value = 'true' },
                        [pscustomobject]@{ name = 'GOOGLE_CLIENT_ID'; value = 'browser-client' }
                    )
                })
            }
        }
    }
}

function New-EmailApp {
    $api = New-ApiApp
    return [pscustomobject]@{
        id = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.App/containerApps/$emailName"
        name = $emailName
        location = 'westeurope'
        properties = [pscustomobject]@{
            managedEnvironmentId = $api.properties.managedEnvironmentId
            template = [pscustomobject]@{
                containers = @([pscustomobject]@{
                    name = $emailName
                    image = $api.properties.template.containers[0].image
                    command = @('python')
                    args = @('-m', 'app.cli', 'run-email-worker')
                })
            }
        }
    }
}

function global:az {
    $call = @($args | ForEach-Object { [string]$_ })
    $global:AzCalls.Add([object]$call)
    $global:LASTEXITCODE = 0
    $name = Get-CallValue $call '--name'
    $operation = "$($call[0]) $($call[1])"
    if ($call[1] -eq 'revision') { $operation = 'containerapp revision list' }

    if ($global:MockReadFailure -and $operation -eq $global:MockReadFailure) {
        $global:LASTEXITCODE = 31
        return
    }
    if (Test-AzWrite $call) {
        $writeKey = if ($call[1] -eq 'secret') { "containerapp secret set:$name" } else { "$operation`:$name" }
        if ($global:MockMutationFailure -eq $writeKey) { $global:LASTEXITCODE = 41 }
        return
    }
    if ($call[0] -eq 'account' -and $call[1] -eq 'show') { return $subscriptionId }
    if ($call[0] -eq 'group' -and $call[1] -eq 'show') { return }
    if ($call[0] -eq 'containerapp' -and $call[1] -eq 'list') {
        return @((New-ApiApp), (New-EmailApp)) | ConvertTo-Json -Depth 15 -Compress
    }
    if ($call[0] -eq 'containerapp' -and $call[1] -eq 'show') {
        if ($name -eq $apiName) { return (New-ApiApp) | ConvertTo-Json -Depth 15 -Compress }
        if ($name -eq $emailName) { return (New-EmailApp) | ConvertTo-Json -Depth 15 -Compress }
        $global:LASTEXITCODE = 3
        return
    }
    if ($call[0] -eq 'containerapp' -and $call[1] -eq 'revision') {
        if ($global:MockRevisionConflict) {
            return @([pscustomobject]@{ name = "$emailName-review-email" }) | ConvertTo-Json -Compress
        }
        return '[]'
    }
    throw "Unexpected fake Azure invocation: $($call -join ' ')"
}

function Invoke-TestApply {
    param(
        [string]$Image = $digestImage,
        [string]$Suffix = 'review',
        [string]$ApiApp = $apiName,
        [string]$EmailApp = $emailName,
        [string]$SimulationApp = $simulationName,
        [string]$AlertApp = $alertName
    )
    $database = ConvertTo-SecureString 'postgresql://test-only' -AsPlainText -Force
    $jwt = ConvertTo-SecureString 'test-jwt-secret-value' -AsPlainText -Force
    $admin = ConvertTo-SecureString 'test-admin-password' -AsPlainText -Force
    $registryPassword = ConvertTo-SecureString 'test-registry-password' -AsPlainText -Force
    & '__SCRIPT__' -BackendImage $Image -RevisionSuffix $Suffix `
        -ResourceGroup $resourceGroup -ApiContainerApp $ApiApp `
        -EmailContainerApp $EmailApp -SimulationContainerApp $SimulationApp `
        -AlertContainerApp $AlertApp -DatabaseUrl $database -JwtSecret $jwt `
        -AdminPassword $admin -RegistryPassword $registryPassword -Apply
}

__BODY__
"""


def run_apply_powershell(body: str) -> subprocess.CompletedProcess[str]:
    command = (
        MOCK_APPLY_HARNESS.replace("__SCRIPT__", SCRIPT.as_posix())
        .replace("__DIGEST_IMAGE__", DIGEST_IMAGE)
        .replace("__BODY__", body)
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result


def test_powershell_preflight_rejects_mutable_images_and_invalid_names():
    run_powershell(
        """
Assert-Throws { Get-ImmutableAcrImage 'example.azurecr.io/energyai/backend:latest' }
Assert-Throws { Assert-ContainerAppName '1invalid' }
Assert-Throws { Assert-ContainerAppName 'a' }
Assert-Throws { Assert-ContainerAppName 'worker_name' }
Assert-Throws { Assert-ContainerAppName ('a' * 33) }
Assert-Throws { Assert-RevisionName 'ca-energyai-worker' '1review' }
Assert-Throws { Assert-RevisionName 'ca-energyai-worker' 'review_name' }
Assert-Throws { Assert-RevisionName ('a' * 32) ('b' * 33) }
"""
    )


def test_powershell_preflight_rejects_duplicate_targets_and_revision_conflicts():
    run_powershell(
        """
Assert-Throws { New-WorkerPlans 'ca-api' 'ca-email' 'ca-worker' 'ca-worker' 'review' }
$plans = New-WorkerPlans 'ca-api' 'ca-email' 'ca-simulation' 'ca-alert' 'review'
$revisions = @{
  'ca-email' = @([pscustomobject]@{ name = 'ca-email-review-email' })
  'ca-simulation' = @()
  'ca-alert' = @()
}
Assert-Throws { Assert-RevisionAvailability $plans $revisions }
"""
    )


def test_non_email_workers_do_not_receive_email_or_google_credentials():
    run_powershell(
        """
$environment = @(
  [pscustomobject]@{ name = 'DATABASE_URL'; secretRef = 'database-url' },
  [pscustomobject]@{ name = 'JWT_SECRET_KEY'; secretRef = 'jwt-secret' },
  [pscustomobject]@{ name = 'ADMIN_PASSWORD'; secretRef = 'admin-password' },
  [pscustomobject]@{ name = 'LEGAL_OWNER_NAME'; value = 'EnergyAI' },
  [pscustomobject]@{ name = 'LEGAL_CONTACT_EMAIL'; value = 'legal@example.test' },
  [pscustomobject]@{ name = 'SUPPORT_EMAIL'; value = 'support@example.test' },
  [pscustomobject]@{ name = 'LEGAL_EFFECTIVE_DATE'; value = '2026-01-01' },
  [pscustomobject]@{ name = 'EMAIL_DELIVERY_ENABLED'; value = 'true' },
  [pscustomobject]@{ name = 'SMTP_USERNAME'; secretRef = 'smtp-username' },
  [pscustomobject]@{ name = 'SMTP_PASSWORD'; secretRef = 'smtp-password' },
  [pscustomobject]@{ name = 'GOOGLE_AUTH_ENABLED'; value = 'true' },
  [pscustomobject]@{ name = 'GOOGLE_CLIENT_ID'; value = 'client-id' }
)
$secrets = @{
  DATABASE_URL = [pscustomobject]@{ Name = 'database-url'; Value = $null }
  JWT_SECRET_KEY = [pscustomobject]@{ Name = 'jwt-secret'; Value = $null }
  ADMIN_PASSWORD = [pscustomobject]@{ Name = 'admin-password'; Value = $null }
}
$configuration = Get-WorkerConfiguration $environment $secrets 'run-simulation-worker'
$names = @($configuration.Environment | ForEach-Object { $_.name })
if ($names -contains 'SMTP_USERNAME' -or $names -contains 'SMTP_PASSWORD' -or $names -contains 'GOOGLE_CLIENT_ID') { throw 'Non-email worker received an API-only credential.' }
if ((($configuration.Environment | Where-Object name -eq 'EMAIL_DELIVERY_ENABLED').value) -ne 'false') { throw 'Non-email worker did not disable email delivery.' }
if ((($configuration.Environment | Where-Object name -eq 'GOOGLE_AUTH_ENABLED').value) -ne 'false') { throw 'Non-email worker did not disable Google authentication.' }
"""
    )


def test_complete_apply_rejects_deterministic_inputs_before_any_azure_write():
    run_apply_powershell(
        r"""
Assert-ScriptFails { Invoke-TestApply -Image 'example.azurecr.io/energyai/backend:latest' } 'immutable ACR image'
Assert-NoAzWrites
$global:AzCalls.Clear()
Assert-ScriptFails { Invoke-TestApply -ApiApp '1invalid' } 'Container App name'
Assert-NoAzWrites
$global:AzCalls.Clear()
Assert-ScriptFails { Invoke-TestApply -Suffix '1invalid' } 'Revision suffix'
Assert-NoAzWrites
$global:AzCalls.Clear()
Assert-ScriptFails { Invoke-TestApply -SimulationApp 'ca-duplicate' -AlertApp 'ca-duplicate' } 'must all be distinct'
Assert-NoAzWrites
"""
    )


def test_complete_apply_read_and_revision_failures_precede_all_writes():
    run_apply_powershell(
        r"""
$global:MockRevisionConflict = $true
Assert-ScriptFails { Invoke-TestApply } 'already exists'
Assert-NoAzWrites
$global:AzCalls.Clear()
$global:MockRevisionConflict = $false
$global:MockReadFailure = 'containerapp list'
Assert-ScriptFails { Invoke-TestApply } 'Unable to list Container Apps'
Assert-NoAzWrites
"""
    )


def test_complete_apply_creates_workers_with_atomic_secrets_and_email_last():
    result = run_apply_powershell(
        r"""
Invoke-TestApply | Out-Null
$writes = @($global:AzCalls | Where-Object { Test-AzWrite $_ })
if ($writes.Count -ne 3) { throw "Expected three writes, observed $($writes.Count)." }
$writeSummary = @($writes | ForEach-Object { "$($_[0]) $($_[1]):$(Get-CallValue $_ '--name')" })
$expectedSummary = @(
    "containerapp create:$simulationName",
    "containerapp create:$alertName",
    "containerapp update:$emailName"
)
if (($writeSummary -join '|') -ne ($expectedSummary -join '|')) {
    throw "Unexpected mutation order: $($writeSummary -join ', ')"
}

$firstWriteIndex = -1
for ($index = 0; $index -lt $global:AzCalls.Count; $index++) {
    if (Test-AzWrite $global:AzCalls[$index]) { $firstWriteIndex = $index; break }
}
if ($firstWriteIndex -lt 1) { throw 'Expected read-only preflight before the first write.' }
for ($index = 0; $index -lt $firstWriteIndex; $index++) {
    if (Test-AzWrite $global:AzCalls[$index]) { throw 'A write occurred inside preflight.' }
}

foreach ($worker in @(
    [pscustomobject]@{ Name = $simulationName; Command = 'run-simulation-worker'; Suffix = 'review-simulation' },
    [pscustomobject]@{ Name = $alertName; Command = 'run-alert-worker'; Suffix = 'review-alert' }
)) {
    $create = @($writes | Where-Object { $_[1] -eq 'create' -and (Get-CallValue $_ '--name') -eq $worker.Name })[0]
    if ($null -eq $create) { throw "Missing create call for $($worker.Name)." }
    if ($create -contains '--yaml') { throw 'New-worker create must not use YAML.' }
    if ($create -contains '--ingress') { throw 'Worker create introduced ingress.' }
    if ((Get-CallValue $create '--image') -ne $digestImage) { throw 'Worker did not use the immutable digest.' }
    if ((Get-CallValue $create '--command') -ne 'python') { throw 'Worker command executable is incorrect.' }
    if ((Get-CallValue $create '--revision-suffix') -ne $worker.Suffix) { throw 'Worker revision suffix is incorrect.' }
    $commandArguments = @(Get-CallSection $create '--args' '--env-vars')
    if (($commandArguments -join '|') -ne ("-m|app.cli|$($worker.Command)")) { throw 'Worker command arguments are incorrect.' }

    $environment = @(Get-CallSection $create '--env-vars' '--secrets')
    foreach ($required in @(
        'DATABASE_URL=secretref:database-url',
        'JWT_SECRET_KEY=secretref:jwt-secret',
        'ADMIN_PASSWORD=secretref:admin-password',
        'EMAIL_DELIVERY_ENABLED=false',
        'GOOGLE_AUTH_ENABLED=false'
    )) {
        if ($environment -notcontains $required) { throw "Missing worker environment binding: $required" }
    }
    if ($environment -match 'SMTP_|GOOGLE_CLIENT_ID') { throw 'Worker inherited SMTP or Google configuration.' }

    $secrets = @(Get-CallSection $create '--secrets' '--registry-server')
    foreach ($secretName in @('database-url', 'jwt-secret', 'admin-password')) {
        if (-not @($secrets | Where-Object { $_ -like "$secretName=*" })) { throw "Missing create-time secret: $secretName" }
    }
    if ($secrets -match 'smtp|google') { throw 'Worker received an unnecessary SMTP or Google secret.' }
    if (-not (Get-CallValue $create '--registry-password')) { throw 'Registry credential was not supplied during create.' }
}

$emailUpdate = $writes[2]
if ((Get-CallValue $emailUpdate '--image') -ne $digestImage) { throw 'Email worker did not use the immutable digest.' }
"""
    )
    combined_output = result.stdout + result.stderr
    for secret_value in (
        "postgresql://test-only",
        "test-jwt-secret-value",
        "test-admin-password",
        "test-registry-password",
    ):
        assert secret_value not in combined_output


def test_complete_apply_surfaces_mutation_failure_without_false_success():
    run_apply_powershell(
        r"""
$global:MockMutationFailure = "containerapp create:$simulationName"
Assert-ScriptFails { Invoke-TestApply } "Azure failed to create $simulationName"
$writes = @($global:AzCalls | Where-Object { Test-AzWrite $_ })
if ($writes.Count -ne 1) { throw "Expected one attempted mutation, observed $($writes.Count)." }
if ((Get-CallValue $writes[0] '--name') -ne $simulationName) { throw 'Unexpected mutation was attempted.' }
if (@($writes | Where-Object { (Get-CallValue $_ '--name') -eq $emailName }).Count) { throw 'Email was mutated after worker creation failed.' }
"""
    )


def test_powershell_default_plan_never_invokes_azure():
    command = f"""
$ErrorActionPreference = 'Stop'
function global:az {{ throw 'Azure must not be called in plan mode.' }}
& '{SCRIPT.as_posix()}' -BackendImage 'example.azurecr.io/energyai/backend:latest' -RevisionSuffix 'review' | Out-Null
"""
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
