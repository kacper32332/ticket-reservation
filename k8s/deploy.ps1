<#
Wdrożenie Ticketline na lokalny klaster k3d - jedna komenda z katalogu głównego repo:

    .\k8s\deploy.ps1                       # budowa obrazów + import do k3d + helm upgrade --install
    .\k8s\deploy.ps1 -SkipBuild            # tylko helm (np. po zmianie values)
    .\k8s\deploy.ps1 -Values values-static.yaml   # scenariusz B (stała liczba podów)

Obrazy mają stały tag :dev, więc po przebudowie skrypt restartuje Deploymenty (rollout restart),
żeby pody wzięły nową wersję obrazu.
#>
param(
    [switch]$SkipBuild,
    [string]$Values = "",
    [string]$Cluster = "ticketline",
    [string]$Release = "ticketline",
    [string]$Namespace = "ticketline"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Krok nie powiódł się: $Name (kod $LASTEXITCODE)" }
}

$context = kubectl config current-context
if ($context -ne "k3d-$Cluster") {
    throw "Aktywny kontekst kubectl to '$context', oczekiwano 'k3d-$Cluster'. Użyj: kubectl config use-context k3d-$Cluster"
}

$services = @("core-api", "booking-api", "worker")

if (-not $SkipBuild) {
    foreach ($svc in $services) {
        $dir = $svc -replace "-", "_"
        Invoke-Step "docker build ticketline/${svc}:dev" {
            docker build -q -t "ticketline/${svc}:dev" -f "backend/$dir/Dockerfile" backend
        }
    }
    $images = $services | ForEach-Object { "ticketline/${_}:dev" }
    Invoke-Step "k3d image import" { k3d image import @images -c $Cluster }
}

$helmArgs = @(
    "upgrade", "--install", $Release, "k8s/ticketline",
    "--namespace", $Namespace, "--create-namespace",
    "--set-file", "postgres.initSql=db/init.sql",
    "--wait", "--timeout", "5m"
)
if ($Values) { $helmArgs += @("-f", "k8s/ticketline/$Values") }
Invoke-Step "helm upgrade --install" { helm @helmArgs }

if (-not $SkipBuild) {
    Invoke-Step "rollout restart" {
        kubectl -n $Namespace rollout restart deployment/core-api deployment/booking-api deployment/worker
    }
    foreach ($svc in $services) {
        Invoke-Step "rollout status $svc" { kubectl -n $Namespace rollout status "deployment/$svc" --timeout=180s }
    }
}

kubectl -n $Namespace get pods,hpa
Write-Host "`nGotowe. API przez Ingress: http://localhost:8080/api/events" -ForegroundColor Green
