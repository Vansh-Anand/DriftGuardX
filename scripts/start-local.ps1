param([int]$ApiPort = 8010, [int]$WebPort = 3010)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
foreach ($port in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is occupied. Choose different -ApiPort and -WebPort values."
    }
}
$python = Join-Path $repo '.venv/Scripts/python.exe'
if (!(Test-Path $python)) { throw 'Run uv sync --frozen --extra dev --extra infra first.' }
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$logs = Join-Path $repo '.local-runtime'
New-Item -ItemType Directory -Force $logs | Out-Null
$env:DGX_MODE = 'development'
$env:APP_ENV = 'local'
$env:ENVIRONMENT = 'local'
$env:AUTH_MODE = 'mock'
$env:DATABASE_URL = 'sqlite+aiosqlite:///./.local-runtime/app.db'
$env:ENABLE_CANARY = 'false'
$env:USE_REAL_RAG_PIPELINE = 'false'
$env:DGX_CAPABILITY_SECRET = [guid]::NewGuid().ToString('N')
$env:DGX_TRANSPORT_KEY = [guid]::NewGuid().ToString('N')
$env:CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort"
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$ApiPort"
$env:NEXT_PUBLIC_DEMO_MODE = 'true'
$api = Start-Process $python -ArgumentList @('-m','uvicorn','apps.api.src.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/api.log" -RedirectStandardError "$logs/api-error.log"
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($api.HasExited) { throw "API exited. See $logs/api-error.log" }
        try {
            Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (!$ready) { throw "API startup timed out. See $logs/api-error.log" }
    $web = Start-Process $npm -ArgumentList @('run','dev','--','--hostname','127.0.0.1','--port',"$WebPort") -WorkingDirectory "$repo/apps/web" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/web.log" -RedirectStandardError "$logs/web-error.log"
    Write-Output "Local research console: http://127.0.0.1:$WebPort"
    Write-Output "API: http://127.0.0.1:$ApiPort (PID $($api.Id)); web launcher PID $($web.Id)"
    Write-Output "Logs: $logs"
} catch {
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
    throw
}
