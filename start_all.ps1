# Secure Audit — Single IDE Terminal Launcher
param(
    [switch]$NewWindows
)

$rootDir = $PSScriptRoot

if ($NewWindows) {
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "🚀 Launching All Secure Audit Services (Separate Windows)" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan

    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\blockchain'; npx ganache --server.host 127.0.0.1 --server.port 8545 --chain.chainId 1337 --wallet.deterministic --database.dbPath ./ganache-data"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\backend'; py -3.10 app.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\bns-backend'; py -3.10 -m uvicorn app.main:app --port 8001 --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\audio-backend'; py -3.10 app.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\best'; .\venv\Scripts\python.exe main.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\photogrammetry-backend'; py -3.10 app.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\audit-frontend'; npm run dev"

    Write-Host "✅ Launched 7 services in separate windows!" -ForegroundColor Green
    Write-Host "🌐 Frontend: http://localhost:5173" -ForegroundColor Yellow
} else {
    # Default: Run everything inside current IDE terminal window
    py -3.10 "$rootDir\start_all.py"
}
