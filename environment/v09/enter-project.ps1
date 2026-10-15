# Dot-source this file: . 'E:\Projects\Quietmirror\_support\enter-project.ps1'
$quietmirrorSupport = $PSScriptRoot
$quietmirrorBase = Split-Path -Parent $quietmirrorSupport
$quietmirrorRepo = Join-Path $quietmirrorBase 'github'
$quietmirrorEnvironment = @{
    TEMP = (Join-Path $quietmirrorSupport 'tmp')
    TMP = (Join-Path $quietmirrorSupport 'tmp')
    XDG_CACHE_HOME = (Join-Path $quietmirrorSupport 'cache')
    PIP_CACHE_DIR = (Join-Path $quietmirrorSupport 'cache\pip')
    UV_CACHE_DIR = (Join-Path $quietmirrorSupport 'cache\uv')
    UV_PYTHON_INSTALL_DIR = (Join-Path $quietmirrorSupport 'tools\python')
    UV_TOOL_DIR = (Join-Path $quietmirrorSupport 'tools\uv')
    UV_TOOL_BIN_DIR = (Join-Path $quietmirrorSupport 'tools\uv-bin')
    PYTHONUSERBASE = (Join-Path $quietmirrorSupport 'tools\python-user')
    PYTHONPYCACHEPREFIX = (Join-Path $quietmirrorSupport 'cache\pycache')
    PYTHONNOUSERSITE = '1'
    npm_config_cache = (Join-Path $quietmirrorSupport 'cache\npm')
    npm_config_prefix = (Join-Path $quietmirrorSupport 'tools\npm-global')
    COREPACK_HOME = (Join-Path $quietmirrorSupport 'tools\corepack')
}
foreach ($quietmirrorName in $quietmirrorEnvironment.Keys) {
    [Environment]::SetEnvironmentVariable($quietmirrorName, $quietmirrorEnvironment[$quietmirrorName], 'Process')
}
Set-Location -LiteralPath $quietmirrorRepo
# Portable CAD configuration and rendering cache are kept on E:.
$env:MPLCONFIGDIR = Join-Path $quietmirrorSupport 'cache\matplotlib'
$env:FREECAD_USER_HOME = Join-Path $quietmirrorSupport 'config\FreeCAD'
$env:FREECAD_USER_DATA = Join-Path $quietmirrorSupport 'config\FreeCAD\data'
$env:FREECAD_USER_TEMP = Join-Path $quietmirrorSupport 'tmp'
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:NUMEXPR_NUM_THREADS = '2'
$env:VTK_SMP_MAX_THREADS = '2'
$env:VTK_SMP_IMPLEMENTATION_TYPE = 'Sequential'
foreach ($quietmirrorCadDir in @($env:MPLCONFIGDIR, $env:FREECAD_USER_HOME, $env:FREECAD_USER_DATA)) {
    New-Item -ItemType Directory -Path $quietmirrorCadDir -Force | Out-Null
}
