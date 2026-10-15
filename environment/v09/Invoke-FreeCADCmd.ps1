param([Parameter(ValueFromRemainingArguments = $true)][string[]]$FreeCADArguments)
. (Join-Path $PSScriptRoot 'enter-project.ps1')
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
& (Join-Path $PSScriptRoot 'tools\FreeCAD\bin\freecadcmd.exe') --user-cfg (Join-Path $PSScriptRoot 'config\FreeCAD\user.cfg') --system-cfg (Join-Path $PSScriptRoot 'config\FreeCAD\system.cfg') @FreeCADArguments
exit $LASTEXITCODE
