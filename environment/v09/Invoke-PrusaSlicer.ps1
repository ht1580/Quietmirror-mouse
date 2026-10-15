param([Parameter(ValueFromRemainingArguments = $true)][string[]]$SlicerArguments)
. (Join-Path $PSScriptRoot 'enter-project.ps1')
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
& (Join-Path $PSScriptRoot 'tools\PrusaSlicer\PrusaSlicer-2.9.6\prusa-slicer-console.exe') --sw-renderer --datadir (Join-Path $PSScriptRoot 'config\PrusaSlicer') --threads 2 @SlicerArguments
exit $LASTEXITCODE
