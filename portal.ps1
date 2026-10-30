# Gestión del Portal de Propietarios desde PowerShell (Windows).
# Uso: .\portal.ps1 <comando>      Ejemplo: .\portal.ps1 instalar
param(
    [Parameter(Position = 0)][string]$Comando = 'ayuda',
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Resto
)
$ErrorActionPreference = 'Stop'
$Raiz  = $PSScriptRoot
$Back  = Join-Path $Raiz 'backend'
$Front = Join-Path $Raiz 'frontend'
$Venv  = Join-Path $Back '.venv'
$Puerto = 8000
if ($env:PUERTO) { $Puerto = [int]$env:PUERTO }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Ok($t)    { Write-Host $t -ForegroundColor Green }
function Falla($t) { Write-Host $t -ForegroundColor Red; exit 1 }

function PyVenv {
    $win = Join-Path $Venv 'Scripts\python.exe'
    if (Test-Path $win) { return $win }
    $nix = Join-Path $Venv 'bin/python'
    if (Test-Path $nix) { return $nix }
    Falla 'No está instalado. Ejecute primero: .\portal.ps1 instalar'
}

function PySistema {
    # Busca un Python real (el alias de Microsoft Store no sirve)
    foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = Get-Command $c[0] -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        $args2 = @()
        if ($c.Count -gt 1) { $args2 = $c[1..($c.Count - 1)] }
        try {
            $v = & $c[0] @args2 -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])' 2>$null
            if ($LASTEXITCODE -eq 0 -and [int]$v -ge 310) { return , $c }
        } catch { }
    }
    Falla "No encontré Python 3.10 o superior. Instálelo con:`n  winget install Python.Python.3.12`nLuego cierre y abra PowerShell."
}

function RutaNpm {
    $n = Get-Command 'npm.cmd' -CommandType Application -ErrorAction SilentlyContinue
    if (-not $n) { $n = Get-Command 'npm' -CommandType Application -ErrorAction SilentlyContinue }
    if (-not $n) { Falla "No encontré Node.js. Instálelo con:`n  winget install OpenJS.NodeJS.LTS`nLuego cierre y abra PowerShell." }
    return ($n | Select-Object -First 1).Source
}

function Correr([string]$exe, [string[]]$argumentos, [string]$dir) {
    Push-Location $dir
    try {
        & $exe @argumentos
        if ($LASTEXITCODE -ne 0) { Falla "Falló: $exe $($argumentos -join ' ')" }
    } finally { Pop-Location }
}

function Instalar {
    $py = PySistema
    $npm = RutaNpm
    Ok '1/3 Entorno de Python'
    if (-not (Test-Path $Venv)) {
        $a = @()
        if ($py.Count -gt 1) { $a = $py[1..($py.Count - 1)] }
        Correr $py[0] ($a + @('-m', 'venv', $Venv)) $Back
    }
    $p = PyVenv
    Correr $p @('-m', 'pip', 'install', '-q', '--upgrade', 'pip') $Back
    Correr $p @('-m', 'pip', 'install', '-q', '-r', 'requirements.txt') $Back
    Ok '2/3 Dependencias del frontend'
    Correr $npm @('install', '--no-audit', '--no-fund', '--loglevel=error') $Front
    Ok '3/3 Compilando el frontend'
    Correr $npm @('run', 'build', '--silent') $Front
    Ok 'Instalación completa.'
}

function Demo {
    Ok 'Creando base de datos con datos de demostración (borra la actual)...'
    Correr (PyVenv) @('seed.py') $Back
}

function Probar { Correr (PyVenv) @('-m', 'pytest', '-q') $Back }

function Compilar {
    Correr (RutaNpm) @('run', 'build', '--silent') $Front
    Ok 'Frontend compilado en frontend\dist'
}

function Iniciar {
    if (-not (Test-Path (Join-Path $Front 'dist'))) { Compilar }
    if (-not (Test-Path (Join-Path $Back 'copropiedad.db')) -and -not $env:DATABASE_URL) { Demo }
    Ok "Portal en http://localhost:$Puerto   (Ctrl+C para detener)"
    Correr (PyVenv) @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Puerto") $Back
}

function Red {
    # Arranca el portal visible para otros equipos de la misma red WiFi (celular, tablet)
    if (-not (Test-Path (Join-Path $Front 'dist'))) { Compilar }
    if (-not (Test-Path (Join-Path $Back 'copropiedad.db')) -and -not $env:DATABASE_URL) { Demo }
    $ips = @()
    try {
        $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
            Select-Object -ExpandProperty IPAddress
    } catch { }
    Ok 'Portal visible en su red WiFi. Abra en el celular (conectado al mismo WiFi):'
    if ($ips) { foreach ($ip in $ips) { Ok "   http://${ip}:$Puerto" } }
    else { Write-Host '   http://<IP-de-este-computador>:8000   (la IP aparece con el comando ipconfig)' }
    Write-Host 'Si Windows pregunta por el firewall, permita el acceso en redes PRIVADAS.' -ForegroundColor Yellow
    Write-Host 'Ctrl+C para detener.'
    Correr (PyVenv) @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', "$Puerto") $Back
}

function Desarrollo {
    Ok "Backend con recarga automática en :$Puerto y frontend en http://localhost:5173"
    $srv = Start-Process -FilePath (PyVenv) -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--reload', '--port', "$Puerto") `
        -WorkingDirectory $Back -NoNewWindow -PassThru
    try { Correr (RutaNpm) @('run', 'dev') $Front }
    finally { if (-not $srv.HasExited) { Stop-Process -Id $srv.Id -Force } }
}

function Admin {
    if ($Resto.Count -lt 2) { Falla 'Uso: .\portal.ps1 admin correo@dominio.co "Nombre Completo"' }
    Correr (PyVenv) @('crear_admin.py', $Resto[0], $Resto[1]) $Back
}

function Conjunto {
    # Pasa los argumentos a backend\conjunto.py: generar, cargar-unidades, plantilla-propietarios...
    $a = @('conjunto.py')
    if ($Resto) { $a += $Resto }
    Correr (PyVenv) $a $Back
}

function Respaldo {
    $dest = Join-Path $Raiz 'respaldos'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $f = Join-Path $dest ("respaldo_{0}.zip" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
    $items = @()
    $db = Join-Path $Back 'copropiedad.db'
    if (Test-Path $db) { $items += $db }
    $up = Join-Path $Back 'uploads'
    if (Test-Path $up) { $items += $up }
    if ($items.Count -eq 0) { Falla 'No hay nada que respaldar todavía.' }
    Compress-Archive -Path $items -DestinationPath $f
    Ok "Respaldo creado: $f"
}

function Api {
    # .\portal.ps1 api <correo> <clave> <GET|POST> <ruta> [json]
    if ($Resto.Count -lt 4) { Falla "Uso: .\portal.ps1 api <correo> <clave> <GET|POST> <ruta> ['json']" }
    $base = "http://localhost:$Puerto"
    $login = @{ email = $Resto[0]; password = $Resto[1] } | ConvertTo-Json
    try {
        $t = Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -Body ([Text.Encoding]::UTF8.GetBytes($login)) -ContentType 'application/json; charset=utf-8'
    } catch { Falla 'No se pudo ingresar. ¿Está corriendo el portal (.\portal.ps1 iniciar) y la clave es correcta?' }
    $h = @{ Authorization = "Bearer $($t.access_token)" }
    try {
        if ($Resto.Count -ge 5) {
            $r = Invoke-RestMethod -Method $Resto[2] -Uri "$base$($Resto[3])" -Headers $h -Body ([Text.Encoding]::UTF8.GetBytes($Resto[4])) -ContentType 'application/json; charset=utf-8'
        } else {
            $r = Invoke-RestMethod -Method $Resto[2] -Uri "$base$($Resto[3])" -Headers $h
        }
        $r | ConvertTo-Json -Depth 10
    } catch {
        $msg = $_.ErrorDetails.Message
        if (-not $msg) { $msg = $_.Exception.Message }
        try { $msg = ($msg | ConvertFrom-Json).detail } catch { }
        Write-Host $msg -ForegroundColor Yellow
    }
}

function Nube {
    # Ejecuta 'admin' o 'conjunto' contra la base de datos de Render desde este computador.
    $archivo = Join-Path $Back '.nube'
    if (-not $Resto -or $Resto.Count -lt 1) { Falla 'Uso: .\portal.ps1 nube conectar "<External Database URL>"  |  nube admin ...  |  nube conjunto ...' }
    $sub = $Resto[0]
    $resto2 = @()
    if ($Resto.Count -gt 1) { $resto2 = $Resto[1..($Resto.Count - 1)] }
    if ($sub -eq 'conectar') {
        if ($resto2.Count -lt 1) { Falla 'Uso: .\portal.ps1 nube conectar "<External Database URL de Render>"' }
        Set-Content -Path $archivo -Value $resto2[0] -Encoding ascii -NoNewline
        Ok 'Conexión guardada en backend\.nube (no se sube a GitHub).'
        return
    }
    if (-not (Test-Path $archivo)) { Falla 'Primero: .\portal.ps1 nube conectar "<External Database URL de Render>"' }
    $env:DATABASE_URL = (Get-Content $archivo -Raw).Trim()
    switch ($sub) {
        'admin'    { $script:Resto = $resto2; Admin }
        'conjunto' { $script:Resto = $resto2; Conjunto }
        default    { Falla "Subcomando desconocido: $sub (use admin o conjunto)" }
    }
}

function Publicar {
    # Corre las pruebas, guarda los cambios y los sube a GitHub. Render redespliega solo.
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { Falla "No encontré git. Instálelo con:`n  winget install Git.Git" }
    Probar
    $msg = 'Actualización del portal'
    if ($Resto -and $Resto.Count -gt 0) { $msg = $Resto -join ' ' }
    Push-Location $Raiz
    try {
        git add -A
        git diff --cached --quiet
        if ($LASTEXITCODE -ne 0) { git commit -m $msg; if ($LASTEXITCODE -ne 0) { Falla 'Falló el commit' } }
        git pull --rebase origin main
        if ($LASTEXITCODE -ne 0) { Falla 'Falló git pull (resuelva el conflicto y repita)' }
        git push origin main
        if ($LASTEXITCODE -ne 0) { Falla 'Falló git push' }
    } finally { Pop-Location }
    Ok 'Subido a GitHub. Render lo despliega en 3-5 minutos.'
}

function Ayuda {
    $lineas = @(
        'Portal de Propietarios - comandos (PowerShell)',
        '',
        '  .\portal.ps1 instalar      Instala dependencias y compila el frontend',
        '  .\portal.ps1 demo          Crea la base con datos de prueba (clave de todos: Demo2026*)',
        '  .\portal.ps1 probar        Ejecuta las 31 pruebas automáticas',
        '  .\portal.ps1 iniciar       Arranca el portal en http://localhost:8000',
        '  .\portal.ps1 red           Arranca el portal para verlo desde el celular en el mismo WiFi',
        '  .\portal.ps1 desarrollo    Backend con recarga + frontend Vite (para modificar código)',
        '  .\portal.ps1 compilar      Vuelve a compilar el frontend',
        '  .\portal.ps1 admin <correo> "<nombre>"   Crea el administrador real',
        '  .\portal.ps1 respaldo      Copia en .zip la base de datos y los archivos subidos',
        '',
        '  En internet (Render):',
        '  .\portal.ps1 publicar "mensaje"     Prueba, sube a GitHub y Render redespliega solo',
        '  .\portal.ps1 nube conectar "<External Database URL>"   Guarda la conexión a la base de Render',
        '  .\portal.ps1 nube admin <correo> "<nombre>"            Crea el administrador en Render',
        '  .\portal.ps1 nube conjunto cargar-unidades --confirmar  (y demás comandos de conjunto)',
        '',
        '  Conjunto real (archivos en backend\datos, que no se suben a GitHub):',
        '  .\portal.ps1 conjunto generar --torres 9 --pisos 6 --por-piso 4',
        '  .\portal.ps1 conjunto cargar-unidades [--confirmar]',
        '  .\portal.ps1 conjunto plantilla-propietarios',
        '  .\portal.ps1 conjunto cargar-propietarios [--confirmar]',
        '  .\portal.ps1 conjunto parqueaderos --tipo carro --cantidad 150 --prefijo C',
        '  .\portal.ps1 conjunto resumen',
        '',
        "  .\portal.ps1 api <correo> <clave> <GET|POST> <ruta> ['json']",
        '       Ejemplo: .\portal.ps1 api admin@conjunto.co Demo2026* GET /api/admin/dashboard'
    )
    $lineas | ForEach-Object { Write-Host $_ }
}

switch ($Comando.ToLower()) {
    'instalar'   { Instalar }
    'demo'       { Demo }
    'probar'     { Probar }
    'compilar'   { Compilar }
    'iniciar'    { Iniciar }
    'red'        { Red }
    'desarrollo' { Desarrollo }
    'admin'      { Admin }
    'respaldo'   { Respaldo }
    'conjunto'   { Conjunto }
    'api'        { Api }
    'nube'       { Nube }
    'publicar'   { Publicar }
    default      { Ayuda }
}
