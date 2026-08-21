[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackendImage,

    [Parameter(Mandatory = $true)]
    [string]$RevisionSuffix,

    [string]$ResourceGroup = 'rg-energyai-pfe',
    [string]$ApiContainerApp = 'ca-energyai-api',
    [string]$EmailContainerApp = 'ca-energyai-email-worker',
    [string]$SimulationContainerApp = 'ca-energyai-simulation-worker',
    [string]$AlertContainerApp = 'ca-energyai-alert-worker',

    [securestring]$DatabaseUrl,
    [securestring]$JwtSecret,
    [securestring]$AdminPassword,
    [securestring]$RegistryPassword,

    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$ImmutableAcrImagePattern = '^(?<registry>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.azurecr\.io)/(?<repository>[a-z0-9](?:[a-z0-9._/-]*[a-z0-9])?)@sha256:(?<digest>[a-fA-F0-9]{64})$'
$AcrRepositoryPattern = '^(?<registry>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.azurecr\.io)/(?<repository>[a-z0-9](?:[a-z0-9._/-]*[a-z0-9])?)(?:@sha256:[a-fA-F0-9]{64}|:[^/@\s]+)?$'

# These are the only application settings a worker may inherit from the API.
# The common settings are required because importing app.database constructs
# Settings and validates deployed database, legal, and enabled-integration config.
$WorkerEnvironmentNames = @(
    'DEBUG', 'DATABASE_URL', 'JWT_SECRET_KEY', 'JWT_ALGORITHM',
    'ACCESS_TOKEN_EXPIRE_MINUTES', 'REFRESH_TOKEN_EXPIRE_DAYS', 'ADMIN_EMAIL',
    'ADMIN_PASSWORD', 'FRONTEND_URL', 'ALERT_WORKER_INTERVAL_SECONDS',
    'SIMULATION_WORKER_INTERVAL_SECONDS', 'FORECAST_168H_ENABLED',
    'FORECAST_30D_ENABLED', 'EMAIL_DELIVERY_ENABLED', 'GOOGLE_AUTH_ENABLED',
    'PUBLIC_FRONTEND_URL', 'EMAIL_FROM_ADDRESS', 'EMAIL_FROM_NAME',
    'EMAIL_REPLY_TO', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME',
    'SMTP_PASSWORD', 'SMTP_USE_TLS', 'SMTP_TIMEOUT_SECONDS',
    'EMAIL_WORKER_POLL_SECONDS', 'EMAIL_LEASE_SECONDS',
    'EMAIL_RETRY_BASE_SECONDS', 'EMAIL_MAX_ATTEMPTS', 'GOOGLE_CLIENT_ID',
    'GOOGLE_CHALLENGE_EXPIRE_MINUTES', 'LEGAL_OWNER_NAME',
    'LEGAL_CONTACT_EMAIL', 'SUPPORT_EMAIL', 'LEGAL_EFFECTIVE_DATE'
)
$WorkerRequiredEnvironmentNames = @(
    'DATABASE_URL', 'JWT_SECRET_KEY', 'ADMIN_PASSWORD', 'LEGAL_OWNER_NAME',
    'LEGAL_CONTACT_EMAIL', 'SUPPORT_EMAIL', 'LEGAL_EFFECTIVE_DATE'
)
$WorkerEmailOnlyEnvironmentNames = @(
    'PUBLIC_FRONTEND_URL', 'EMAIL_FROM_ADDRESS', 'EMAIL_FROM_NAME',
    'EMAIL_REPLY_TO', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME',
    'SMTP_PASSWORD', 'SMTP_USE_TLS', 'SMTP_TIMEOUT_SECONDS',
    'EMAIL_WORKER_POLL_SECONDS', 'EMAIL_LEASE_SECONDS',
    'EMAIL_RETRY_BASE_SECONDS', 'EMAIL_MAX_ATTEMPTS'
)
$WorkerGoogleOnlyEnvironmentNames = @(
    'GOOGLE_CLIENT_ID', 'GOOGLE_CHALLENGE_EXPIRE_MINUTES'
)

function Get-PlainText([securestring]$Value) {
    if ($null -eq $Value) { return $null }
    return [System.Net.NetworkCredential]::new('', $Value).Password
}

function Require-Value([string]$Name, [securestring]$Value) {
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace((Get-PlainText $Value))) {
        throw "-Apply requires -$Name. Pass the existing secret without writing it to this repository."
    }
}

function Get-AzJson([string[]]$Arguments, [string]$FailureMessage) {
    $output = & az @Arguments
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
    return $output | ConvertFrom-Json
}

function Assert-ContainerAppName([string]$Name) {
    if ($Name -notmatch '^[a-z][a-z0-9-]{0,30}[a-z0-9]$' -or $Name.Contains('--')) {
        throw "Container App name '$Name' is not valid for Azure Container Apps."
    }
}

function Assert-RevisionName([string]$AppName, [string]$Suffix) {
    if ($Suffix -notmatch '^[a-z](?:[a-z0-9-]*[a-z0-9])?$' -or $Suffix.Contains('--')) {
        throw "Revision suffix '$Suffix' is not valid for Azure Container Apps."
    }
    $revisionName = "$AppName-$Suffix"
    if ($revisionName.Length -gt 64 -or $revisionName -notmatch '^[a-z][a-z0-9-]*[a-z0-9]$') {
        throw "Generated revision name '$revisionName' is not valid for Azure Container Apps."
    }
}

function Get-ImmutableAcrImage([string]$Image) {
    if ($Image -notmatch $ImmutableAcrImagePattern) {
        throw '-Apply requires an immutable ACR image in repository@sha256:<64 hexadecimal characters> form.'
    }
    return [pscustomobject]@{
        Registry = $Matches.registry
        Repository = $Matches.repository
    }
}

function Get-AcrRepository([string]$Image, [string]$ResourceName) {
    if ($Image -notmatch $AcrRepositoryPattern) {
        throw "$ResourceName does not use a parseable Azure Container Registry image."
    }
    return [pscustomobject]@{ Registry = $Matches.registry; Repository = $Matches.repository }
}

function Assert-ResourceScope($Resource, [string]$Name, [string]$SubscriptionId, [string]$Group) {
    $expectedId = "/subscriptions/$SubscriptionId/resourceGroups/$Group/providers/Microsoft.App/containerApps/$Name"
    if ($null -eq $Resource -or -not [string]::Equals([string]$Resource.id, $expectedId, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Azure returned an unexpected resource for '$Name'."
    }
}

function Assert-SameAcrRepository($Expected, $Actual, [string]$ResourceName) {
    if (-not [string]::Equals($Expected.Registry, $Actual.Registry, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($Expected.Repository, $Actual.Repository, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The requested backend image does not match the registry and repository configured by $ResourceName."
    }
}

function Get-ContainerCommand($ContainerApp) {
    $container = @($ContainerApp.properties.template.containers)[0]
    return @($container.command) + @($container.args)
}

function New-WorkerPlans(
    [string]$ApiName,
    [string]$EmailName,
    [string]$SimulationName,
    [string]$AlertName,
    [string]$Suffix
) {
    $allNames = @($ApiName, $EmailName, $SimulationName, $AlertName)
    foreach ($name in $allNames) { Assert-ContainerAppName $name }
    if (($allNames | Select-Object -Unique).Count -ne $allNames.Count) {
        throw 'API, email, simulation, and alert Container App names must all be distinct.'
    }
    $plans = @(
        [pscustomobject]@{ Name = $EmailName; Command = 'run-email-worker'; RevisionSuffix = "$Suffix-email"; Existing = $true; WorkerConfiguration = $null; AppSecretBindings = @(); RegistryBinding = $null; Registry = $null; ManagedEnvironmentId = $null; SecretBindings = @(); Definition = $null },
        [pscustomobject]@{ Name = $SimulationName; Command = 'run-simulation-worker'; RevisionSuffix = "$Suffix-simulation"; Existing = $false; WorkerConfiguration = $null; AppSecretBindings = @(); RegistryBinding = $null; Registry = $null; ManagedEnvironmentId = $null; SecretBindings = @(); Definition = $null },
        [pscustomobject]@{ Name = $AlertName; Command = 'run-alert-worker'; RevisionSuffix = "$Suffix-alert"; Existing = $false; WorkerConfiguration = $null; AppSecretBindings = @(); RegistryBinding = $null; Registry = $null; ManagedEnvironmentId = $null; SecretBindings = @(); Definition = $null }
    )
    foreach ($plan in $plans) { Assert-RevisionName $plan.Name $plan.RevisionSuffix }
    return $plans
}

function Assert-RevisionAvailability($Plans, [hashtable]$RevisionsByName) {
    foreach ($plan in $Plans) {
        $revisionName = "$($plan.Name)-$($plan.RevisionSuffix)"
        foreach ($revision in @($RevisionsByName[$plan.Name])) {
            if ([string]::Equals([string]$revision.name, $revisionName, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Generated revision '$revisionName' already exists for $($plan.Name). Choose a new RevisionSuffix."
            }
        }
    }
}

function Assert-CompatibleWorkerTarget($Target, $Api, $Plan) {
    $expected = @('python', '-m', 'app.cli', $Plan.Command)
    if (((Get-ContainerCommand $Target) -join "`0") -ne ($expected -join "`0")) {
        throw "$($Plan.Name) does not have the expected $($Plan.Command) command."
    }
    if (-not [string]::Equals([string]$Target.properties.managedEnvironmentId, [string]$Api.properties.managedEnvironmentId, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$($Plan.Name) is attached to a different managed environment than $($Api.name)."
    }
    $identityType = [string]$Target.identity.type
    if (-not [string]::IsNullOrWhiteSpace($identityType) -and $identityType -ne 'None') {
        throw "$($Plan.Name) has an identity that this worker definition would not preserve."
    }
}

function Test-EnabledValue($EnvironmentByName, [string]$Name) {
    $item = $EnvironmentByName[$Name]
    return $null -ne $item -and $null -ne $item.value -and (([string]$item.value) -match '^(?i:true|1|yes)$')
}

function Get-WorkerConfiguration($ApiEnvironment, [hashtable]$SecretInputs, [string]$Command) {
    $environmentByName = @{}
    foreach ($item in @($ApiEnvironment)) { $environmentByName[$item.name] = $item }
    $requiredNames = @($WorkerRequiredEnvironmentNames)
    $isEmailWorker = $Command -eq 'run-email-worker'
    if ($isEmailWorker -and (Test-EnabledValue $environmentByName 'EMAIL_DELIVERY_ENABLED')) {
        $requiredNames += @('PUBLIC_FRONTEND_URL', 'EMAIL_FROM_ADDRESS', 'SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD')
    }

    $environment = @()
    $secretBindings = @()
    foreach ($name in $WorkerEnvironmentNames) {
        $item = $environmentByName[$name]
        if ($null -eq $item) { continue }
        if ($name -eq 'EMAIL_DELIVERY_ENABLED') {
            $environment += @{ name = $name; value = if ($isEmailWorker) { [string]$item.value } else { 'false' } }
            continue
        }
        if ($name -eq 'GOOGLE_AUTH_ENABLED') {
            # API-only identity configuration is not needed by a background loop.
            $environment += @{ name = $name; value = 'false' }
            continue
        }
        if ((-not $isEmailWorker -and $name -in $WorkerEmailOnlyEnvironmentNames) -or $name -in $WorkerGoogleOnlyEnvironmentNames) {
            continue
        }
        if ($item.secretRef) {
            if (-not $SecretInputs.ContainsKey($name)) {
                throw "Worker configuration cannot safely satisfy API secret reference '$name'."
            }
            $binding = $SecretInputs[$name]
            if (-not [string]::Equals([string]$item.secretRef, [string]$binding.Name, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "API secret reference for '$name' must be '$($binding.Name)' for worker deployment."
            }
            $environment += @{ name = $name; secretRef = $binding.Name }
            $secretBindings += $binding
        } elseif ($null -ne $item.value) {
            $environment += @{ name = $name; value = [string]$item.value }
        }
    }
    $configuredNames = @($environment | ForEach-Object { $_.name })
    foreach ($name in ($requiredNames | Select-Object -Unique)) {
        if ($name -notin $configuredNames) {
            throw "Worker configuration requires API environment variable '$name'."
        }
    }
    return [pscustomobject]@{
        Environment = $environment
        SecretBindings = @($secretBindings | Sort-Object Name -Unique)
    }
}

function New-WorkerDefinition($Plan, $Api, $Registry, $WorkerConfiguration) {
    if ([string]::IsNullOrWhiteSpace([string]$Api.location) -or [string]::IsNullOrWhiteSpace([string]$Api.properties.managedEnvironmentId)) {
        throw 'API location or managed environment is missing; worker definition cannot be generated.'
    }
    if (@($WorkerConfiguration.Environment).Count -eq 0 -or @($WorkerConfiguration.SecretBindings).Count -eq 0) {
        throw "Worker definition for $($Plan.Name) is incomplete."
    }
    return [ordered]@{
        location = $Api.location
        properties = [ordered]@{
            managedEnvironmentId = $Api.properties.managedEnvironmentId
            configuration = [ordered]@{
                activeRevisionsMode = 'single'
                registries = @(@{
                    server = $Registry.server
                    username = $Registry.username
                    passwordSecretRef = 'registry-password'
                })
            }
            template = [ordered]@{
                revisionSuffix = $Plan.RevisionSuffix
                containers = @(@{
                    name = $Plan.Name
                    image = $BackendImage
                    command = @('python', '-m', 'app.cli', $Plan.Command)
                    env = @($WorkerConfiguration.Environment)
                })
                scale = @{ minReplicas = 1; maxReplicas = 1 }
            }
        }
    }
}

function New-SecretArguments($SecretBindings) {
    $arguments = @()
    foreach ($binding in @($SecretBindings)) {
        $arguments += "$($binding.Name)=$(Get-PlainText $binding.Value)"
    }
    return $arguments
}

function New-WorkerEnvironmentArguments($Environment) {
    $arguments = @()
    foreach ($item in @($Environment)) {
        if ($item.secretRef) {
            $arguments += "$($item.name)=secretref:$($item.secretRef)"
        } else {
            $arguments += "$($item.name)=$($item.value)"
        }
    }
    return $arguments
}

function Set-WorkerSecrets($Plan) {
    $secretArguments = New-SecretArguments $Plan.SecretBindings
    & az containerapp secret set --subscription $subscriptionId --resource-group $ResourceGroup --name $Plan.Name --secrets @secretArguments --output none
    if ($LASTEXITCODE -ne 0) { throw "Azure failed to set secrets for $($Plan.Name)." }
}

function Update-ExistingWorker($Plan) {
    $path = [System.IO.Path]::GetTempFileName()
    $Plan.Definition | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    try {
        Set-WorkerSecrets $Plan
        & az containerapp update --subscription $subscriptionId --resource-group $ResourceGroup --name $Plan.Name --yaml $path --output none
        if ($LASTEXITCODE -ne 0) { throw "Azure failed to update $($Plan.Name)." }
    } finally {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

function Create-NewWorker($Plan) {
    $environmentArguments = New-WorkerEnvironmentArguments $Plan.WorkerConfiguration.Environment
    $secretArguments = New-SecretArguments $Plan.AppSecretBindings
    $registryPasswordValue = Get-PlainText $Plan.RegistryBinding.Value
    & az containerapp create `
        --subscription $subscriptionId `
        --resource-group $ResourceGroup `
        --name $Plan.Name `
        --environment $Plan.ManagedEnvironmentId `
        --image $BackendImage `
        --command python `
        --args '-m' app.cli $Plan.Command `
        --env-vars @environmentArguments `
        --secrets @secretArguments `
        --registry-server $Plan.Registry.server `
        --registry-username $Plan.Registry.username `
        --registry-password $registryPasswordValue `
        --revision-suffix $Plan.RevisionSuffix `
        --min-replicas 1 `
        --max-replicas 1 `
        --revisions-mode single `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "Azure failed to create $($Plan.Name)." }
}

if (-not $Apply) {
    Write-Host 'Plan only; no Azure resource will be changed.'
    Write-Host "- Update $EmailContainerApp to $BackendImage."
    Write-Host "- Create or update $SimulationContainerApp (one always-on replica) running run-simulation-worker."
    Write-Host "- Create or update $AlertContainerApp (one always-on replica) running run-alert-worker."
    Write-Host 'Re-run with -Apply, an immutable ACR digest image, and the existing application/registry secrets after review.'
    return
}

# Validate deterministic inputs before reading credentials or Azure state.
$backendImageParts = Get-ImmutableAcrImage $BackendImage
$workerPlans = New-WorkerPlans $ApiContainerApp $EmailContainerApp $SimulationContainerApp $AlertContainerApp $RevisionSuffix
$secretInputs = @{
    DATABASE_URL = [pscustomobject]@{ Name = 'database-url'; Value = $DatabaseUrl }
    JWT_SECRET_KEY = [pscustomobject]@{ Name = 'jwt-secret'; Value = $JwtSecret }
    ADMIN_PASSWORD = [pscustomobject]@{ Name = 'admin-password'; Value = $AdminPassword }
}

# All Azure reads and definition validation finish before the first mutation.
$subscriptionId = (& az account show --query id --output tsv).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($subscriptionId)) {
    throw 'Unable to determine the selected Azure subscription.'
}
& az group show --subscription $subscriptionId --name $ResourceGroup --output none
if ($LASTEXITCODE -ne 0) { throw "Unable to read resource group '$ResourceGroup' in the selected subscription." }

$apps = @(Get-AzJson @('containerapp', 'list', '--subscription', $subscriptionId, '--resource-group', $ResourceGroup, '--output', 'json') 'Unable to list Container Apps for preflight validation.')
$appsByName = @{}
foreach ($app in $apps) { $appsByName[$app.name] = $app }
$api = Get-AzJson @('containerapp', 'show', '--subscription', $subscriptionId, '--resource-group', $ResourceGroup, '--name', $ApiContainerApp, '--output', 'json') "Unable to read $ApiContainerApp."
$email = Get-AzJson @('containerapp', 'show', '--subscription', $subscriptionId, '--resource-group', $ResourceGroup, '--name', $EmailContainerApp, '--output', 'json') "Unable to read $EmailContainerApp."
Assert-ResourceScope $api $ApiContainerApp $subscriptionId $ResourceGroup
Assert-ResourceScope $email $EmailContainerApp $subscriptionId $ResourceGroup

$targetsByName = @{ $EmailContainerApp = $email }
foreach ($plan in $workerPlans | Select-Object -Skip 1) {
    if ($appsByName.ContainsKey($plan.Name)) {
        $target = Get-AzJson @('containerapp', 'show', '--subscription', $subscriptionId, '--resource-group', $ResourceGroup, '--name', $plan.Name, '--output', 'json') "Unable to read $($plan.Name)."
        Assert-ResourceScope $target $plan.Name $subscriptionId $ResourceGroup
        Assert-CompatibleWorkerTarget $target $api $plan
        $targetsByName[$plan.Name] = $target
        $plan.Existing = $true
    }
}

$revisionsByName = @{}
foreach ($plan in $workerPlans) {
    if ($targetsByName.ContainsKey($plan.Name)) {
        $revisionsByName[$plan.Name] = @(Get-AzJson @('containerapp', 'revision', 'list', '--subscription', $subscriptionId, '--resource-group', $ResourceGroup, '--name', $plan.Name, '--output', 'json') "Unable to list revisions for $($plan.Name).")
    } else {
        $revisionsByName[$plan.Name] = @()
    }
}
Assert-RevisionAvailability $workerPlans $revisionsByName

$apiContainer = @($api.properties.template.containers)[0]
$apiImage = Get-AcrRepository ([string]$apiContainer.image) $ApiContainerApp
Assert-SameAcrRepository $backendImageParts $apiImage $ApiContainerApp
$registry = @($api.properties.configuration.registries)[0]
if ($null -eq $registry -or [string]::IsNullOrWhiteSpace($registry.server) -or [string]::IsNullOrWhiteSpace($registry.username) -or
    -not [string]::Equals([string]$registry.server, $backendImageParts.Registry, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'The API app does not expose a compatible reusable ACR registry configuration.'
}
if (((Get-ContainerCommand $email) -join "`0") -ne (@('python', '-m', 'app.cli', 'run-email-worker') -join "`0")) {
    throw "$EmailContainerApp does not have the expected email worker command."
}

$registryBinding = [pscustomobject]@{ Name = 'registry-password'; Value = $RegistryPassword }
foreach ($plan in $workerPlans | Select-Object -Skip 1) {
    $workerConfiguration = Get-WorkerConfiguration $apiContainer.env $secretInputs $plan.Command
    $plan.WorkerConfiguration = $workerConfiguration
    $plan.AppSecretBindings = @($workerConfiguration.SecretBindings)
    $plan.RegistryBinding = $registryBinding
    $plan.Registry = $registry
    $plan.ManagedEnvironmentId = $api.properties.managedEnvironmentId
    $plan.SecretBindings = @($plan.AppSecretBindings) + @($registryBinding)
    foreach ($binding in $plan.SecretBindings) { Require-Value $binding.Name $binding.Value }
    $plan.Definition = New-WorkerDefinition $plan $api $registry $workerConfiguration
    # Serialize in memory now so invalid definitions cannot be discovered after a mutation.
    $null = $plan.Definition | ConvertTo-Json -Depth 12
}

Write-Host "Preflight passed for subscription $subscriptionId. Applying worker revisions."
foreach ($plan in $workerPlans | Select-Object -Skip 1) {
    if ($plan.Existing) {
        Update-ExistingWorker $plan
    } else {
        Create-NewWorker $plan
    }
}
& az containerapp update --subscription $subscriptionId --resource-group $ResourceGroup --name $EmailContainerApp --image $BackendImage --revision-suffix $workerPlans[0].RevisionSuffix --min-replicas 1 --max-replicas 1 --output none
if ($LASTEXITCODE -ne 0) { throw "Azure failed to update $EmailContainerApp." }
Write-Host 'Defense worker revisions applied. Verify /api/v1/system/ready and the worker heartbeats before proceeding.'
