param([switch]$Lan)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$logDirectory = Join-Path $root '.local-logs'
$started = @()

function Fail($message) { throw $message }

function Find-Python {
    $userPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path $userPython) { return $userPython }
    $candidates = @(
        @{ command = 'py'; arguments = @('-3.12') },
        @{ command = 'py'; arguments = @('-3') },
        @{ command = 'python'; arguments = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.command -ErrorAction SilentlyContinue)) { continue }
        try {
            $arguments = $candidate.arguments
            $path = & $candidate.command @arguments -c 'import sys; print(sys.executable if sys.version_info >= (3, 12) else "")' 2>$null
            if ($LASTEXITCODE -eq 0 -and $path -and (Test-Path $path.Trim())) { return $path.Trim() }
        } catch { }
    }
    Fail 'Python 3.12 or newer is required. Install Python from python.org, then run run-local.cmd again.'
}

function Free-Port([int]$first) {
    for ($port = $first; $port -lt $first + 30; $port++) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
        try { $listener.Start(); return $port }
        catch { }
        finally { $listener.Stop() }
    }
    Fail "No free local port found near $first."
}

function Load-Env($path) {
    if (-not (Test-Path $path)) { return }
    foreach ($line in [System.IO.File]::ReadAllLines($path)) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        $parts = $line.Split('=', 2)
        if ($parts.Count -ne 2) { continue }
        $name = $parts[0].Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { continue }
        $value = $parts[1].Trim()
        if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[-1] -eq '"') -or ($value[0] -eq "'" -and $value[-1] -eq "'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

function Add-Origin($current, $origin) {
    $values = @($current -split ',' | Where-Object { $_ })
    if ($values -notcontains $origin) { $values += $origin }
    return ($values -join ',')
}

function Get-LanAddresses {
    $addresses = foreach ($adapter in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        if ($adapter.OperationalStatus -ne 'Up' -or $adapter.NetworkInterfaceType -notin @('Ethernet', 'Wireless80211') -or $adapter.Name -match '^(vEthernet|WSL|Docker)') { continue }
        foreach ($unicast in $adapter.GetIPProperties().UnicastAddresses) {
            $address = $unicast.Address
            if ($address.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and
                -not [Net.IPAddress]::IsLoopback($address) -and
                -not $address.ToString().StartsWith('169.254.')) {
                $address.ToString()
            }
        }
    }
    return @($addresses | Sort-Object -Unique)
}

function Wait-For-Http($url, $process, $log) {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($process.HasExited) { Fail "A server exited during startup. See $log" }
        try {
            $request = [Net.WebRequest]::Create($url)
            $request.Timeout = 1000
            $response = $request.GetResponse()
            $response.Close()
            return
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Fail "Server did not respond at $url. See $log"
}

try {
    $localTemp = Join-Path $root '.local-tmp'
    New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
    $env:TEMP = $localTemp
    $env:TMP = $localTemp
    $env:PIP_CACHE_DIR = Join-Path $root '.pip-cache'
    $env:npm_config_cache = Join-Path $root '.npm-cache'
    $python = Find-Python
    if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        Fail 'Node.js 22 or newer is required. Install it from nodejs.org, then run run-local.cmd again.'
    }
    $nodeMajor = [int]((& node --version).TrimStart('v').Split('.')[0])
    if ($nodeMajor -lt 22) { Fail 'Node.js 22 or newer is required.' }

    Load-Env (Join-Path $root '.env')
    # Docker's /data path does not exist on Windows; local runs keep a separate SQLite file.
    if (-not $env:SQLITE_PATH -or $env:SQLITE_PATH -eq '/data/db.sqlite3') {
        $env:SQLITE_PATH = Join-Path $backend 'db.sqlite3'
    }
    $apiPort = Free-Port 8000
    $webPort = Free-Port 5173
    $origin = "http://127.0.0.1:$webPort"
    $env:DJANGO_CSRF_TRUSTED_ORIGINS = Add-Origin $env:DJANGO_CSRF_TRUSTED_ORIGINS $origin
    $env:CORS_ALLOWED_ORIGINS = Add-Origin $env:CORS_ALLOWED_ORIGINS $origin
    $lanAddresses = @()
    if ($Lan) {
        $lanAddresses = @(Get-LanAddresses)
        foreach ($address in $lanAddresses) {
            $lanOrigin = "http://${address}:$webPort"
            $env:DJANGO_CSRF_TRUSTED_ORIGINS = Add-Origin $env:DJANGO_CSRF_TRUSTED_ORIGINS $lanOrigin
            $env:CORS_ALLOWED_ORIGINS = Add-Origin $env:CORS_ALLOWED_ORIGINS $lanOrigin
        }
    }
    $env:API_PROXY_TARGET = "http://127.0.0.1:$apiPort"

    $venvPython = Join-Path $backend '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creating Python virtual environment...'
        & $python -m venv (Join-Path $backend '.venv')
        if ($LASTEXITCODE -ne 0) { Fail 'Could not create the Python virtual environment.' }
    }
    $hasPip = $false
    try { & $venvPython -m pip --version *> $null; $hasPip = $LASTEXITCODE -eq 0 } catch { }
    if (-not $hasPip) {
        & $venvPython -m ensurepip --upgrade --default-pip
        if ($LASTEXITCODE -ne 0) { Fail 'Could not install pip into the Python virtual environment.' }
    }
    $requirements = Join-Path $backend 'requirements.txt'
    $requirementsHash = (Get-FileHash $requirements -Algorithm SHA256).Hash
    $requirementsMarker = Join-Path $backend '.venv\requirements.sha256'
    if (-not (Test-Path $requirementsMarker) -or (Get-Content $requirementsMarker -Raw).Trim() -ne $requirementsHash) {
        Write-Host 'Installing Python dependencies...'
        & $venvPython -m pip install -r $requirements
        if ($LASTEXITCODE -ne 0) { Fail 'Python dependency installation failed.' }
        [System.IO.File]::WriteAllText($requirementsMarker, $requirementsHash)
    }

    $vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
    $lockHash = (Get-FileHash (Join-Path $frontend 'package-lock.json') -Algorithm SHA256).Hash
    $nodeMarker = Join-Path $frontend 'node_modules\.phinance-lock.sha256'
    if (-not (Test-Path $vite) -or -not (Test-Path $nodeMarker) -or (Get-Content $nodeMarker -Raw).Trim() -ne $lockHash) {
        Write-Host 'Installing frontend dependencies...'
        Push-Location $frontend
        try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { Fail 'Frontend dependency installation failed.' } }
        finally { Pop-Location }
        [System.IO.File]::WriteAllText($nodeMarker, $lockHash)
    }

    Write-Host 'Applying database migrations...'
    Push-Location $backend
    try { & $venvPython manage.py migrate --noinput; if ($LASTEXITCODE -ne 0) { Fail 'Database migration failed.' } }
    finally { Pop-Location }

    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $apiLog = Join-Path $logDirectory 'backend.log'
    $webLog = Join-Path $logDirectory 'frontend.log'
    $api = Start-Process -FilePath $venvPython -ArgumentList @('manage.py', 'runserver', '--noreload', "127.0.0.1:$apiPort") -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput $apiLog -RedirectStandardError (Join-Path $logDirectory 'backend-error.log') -PassThru
    $started += $api
    Wait-For-Http "http://127.0.0.1:$apiPort/api/auth/csrf/" $api $apiLog
    $webHost = if ($Lan) { '0.0.0.0' } else { '127.0.0.1' }
    $web = Start-Process -FilePath (Get-Command node).Source -ArgumentList @($vite, '--host', $webHost, '--port', "$webPort", '--strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput $webLog -RedirectStandardError (Join-Path $logDirectory 'frontend-error.log') -PassThru
    $started += $web
    Wait-For-Http "$origin/" $web $webLog
    if ($env:NAVASAN_API_KEY) {
        $gold = Start-Process -FilePath $venvPython -ArgumentList @('manage.py', 'update_gold_price', '--loop') -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'gold.log') -RedirectStandardError (Join-Path $logDirectory 'gold-error.log') -PassThru
        $started += $gold
        Write-Host 'Gold price updater started.'
    }
    Write-Host "Phinance is running at $origin/"
    if ($Lan) {
        foreach ($address in $lanAddresses) { Write-Host "LAN: http://${address}:$webPort/" }
        if (-not $lanAddresses) { Write-Host 'No LAN IPv4 address found. Connect to Wi-Fi or Ethernet and restart.' }
    }
    Write-Host "Backend API: http://127.0.0.1:$apiPort/api/"
    Write-Host 'Press Ctrl+C to stop. Logs are in .local-logs.'
    while ($true) {
        Start-Sleep -Seconds 2
        if ($api.HasExited -or $web.HasExited) { Fail 'A server stopped unexpectedly. Check .local-logs.' }
    }
} catch {
    Write-Host "Startup stopped: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    foreach ($process in $started) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
}
