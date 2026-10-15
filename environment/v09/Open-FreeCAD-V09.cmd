@echo off
set "TEMP=E:\Projects\Quietmirror\_support\tmp"
set "TMP=E:\Projects\Quietmirror\_support\tmp"
set "FREECAD_USER_HOME=E:\Projects\Quietmirror\_support\config\FreeCAD"
set "FREECAD_USER_DATA=E:\Projects\Quietmirror\_support\config\FreeCAD\data"
set "FREECAD_USER_TEMP=E:\Projects\Quietmirror\_support\tmp"
start "" "E:\Projects\Quietmirror\_support\tools\FreeCAD\bin\FreeCAD.exe" --user-cfg "E:\Projects\Quietmirror\_support\config\FreeCAD\user.cfg" --system-cfg "E:\Projects\Quietmirror\_support\config\FreeCAD\system.cfg" "E:\Projects\Quietmirror\github\exports\v09\quietmirror_V0.9.FCStd"
