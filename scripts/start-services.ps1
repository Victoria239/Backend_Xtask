# ═══════════════════════════════════════════════════════════════
# XTask - Start all microservices locally (proxy mode)
# Usage: .\scripts\start-services.ps1
# Stop:  .\scripts\start-services.ps1 -Stop
# ═══════════════════════════════════════════════════════════════

param(
    [switch]$Stop
)

$services = @(
    @{ Name = "auth";       Module = "services.auth.main:app";       Port = 8001 },
    @{ Name = "projects";   Module = "services.projects.main:app";   Port = 8002 },
    @{ Name = "employees";  Module = "services.employees.main:app";  Port = 8003 },
    @{ Name = "finance";    Module = "services.finance.main:app";    Port = 8004 },
    @{ Name = "payroll";    Module = "services.payroll.main:app";    Port = 8005 },
    @{ Name = "kpis";       Module = "services.kpis.main:app";       Port = 8006 },
    @{ Name = "skills";     Module = "services.skills.main:app";     Port = 8007 },
    @{ Name = "dashboard";  Module = "services.dashboard.main:app";  Port = 8008 }
)

$gatewayPort = 8000

if ($Stop) {
    Write-Host "`n🛑 Stopping all services..." -ForegroundColor Red
    foreach ($svc in $services) {
        $conn = Get-NetTCPConnection -LocalPort $svc.Port -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped $($svc.Name) (port $($svc.Port))" -ForegroundColor Yellow
        }
    }
    $gwConn = Get-NetTCPConnection -LocalPort $gatewayPort -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($gwConn) {
        Stop-Process -Id $gwConn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "  Stopped gateway (port $gatewayPort)" -ForegroundColor Yellow
    }
    Write-Host "All services stopped.`n" -ForegroundColor Green
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " XTask Microservices - Local Development" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════`n" -ForegroundColor Cyan

# Start each microservice
foreach ($svc in $services) {
    Write-Host "  Starting $($svc.Name) on port $($svc.Port)..." -ForegroundColor Green
    Start-Process -NoNewWindow -FilePath "uvicorn" `
        -ArgumentList "$($svc.Module)", "--host", "0.0.0.0", "--port", "$($svc.Port)", "--reload", "--no-access-log" `
        -WorkingDirectory $projectDir `
        -RedirectStandardOutput "NUL"
    Start-Sleep -Milliseconds 500
}

Write-Host "`n  Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start gateway in proxy mode
Write-Host "  Starting gateway (proxy mode) on port $gatewayPort..." -ForegroundColor Cyan
$env:GATEWAY_MODE = "proxy"
Start-Process -NoNewWindow -FilePath "uvicorn" `
    -ArgumentList "gateway.main:app", "--host", "0.0.0.0", "--port", "$gatewayPort", "--reload", "--no-access-log" `
    -WorkingDirectory $projectDir `
    -RedirectStandardOutput "NUL"

Start-Sleep -Seconds 2

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " All services running!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Gateway:    http://localhost:$gatewayPort" -ForegroundColor White
foreach ($svc in $services) {
    Write-Host "  $($svc.Name.PadRight(12)) http://localhost:$($svc.Port)" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "  Health:     http://localhost:$gatewayPort/api/health" -ForegroundColor White
Write-Host "  Services:   http://localhost:$gatewayPort/api/health/services" -ForegroundColor White
Write-Host "  Docs:       http://localhost:$gatewayPort/api/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Stop all:   .\scripts\start-services.ps1 -Stop" -ForegroundColor Yellow
Write-Host ""
