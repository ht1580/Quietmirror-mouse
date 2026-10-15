# CAD environment preparation status

Verified 2026-10-15 in the user's existing Windows session. All project downloads, extracted tools, dependencies, configuration, generated test files, and caches are under E:\Projects\Quietmirror\_support. No system packages, graphics driver, registry settings, or global environment settings were changed.

## Tools

- Existing reusable interpreter: D:\python\python.exe, Python 3.12.0. No new interpreter installation.
- Project interpreter: E:\Projects\Quietmirror\_support\venv\Scripts\python.exe.
- FreeCAD portable: E:\Projects\Quietmirror\_support\tools\FreeCAD\bin\freecadcmd.exe; version 1.1.4, revision 20260928, commit 4fd3bf320d9566a27e60069fc8387448aaa3a094.
- FreeCAD GUI executable (not opened): E:\Projects\Quietmirror\_support\tools\FreeCAD\bin\freecad.exe.
- PrusaSlicer portable: E:\Projects\Quietmirror\_support\tools\PrusaSlicer\PrusaSlicer-2.9.6\prusa-slicer-console.exe; version 2.9.6.
- Existing Windows tar.exe was used to extract both archives; no additional archiver installed. Existing WinRAR was located but not needed. uv was not installed because the existing Python and pip suffice.

## Official download sources and integrity

- FreeCAD official release: https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4
- Package: https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD_1.1.4-Windows-x86_64-py311.7z
- Archive: E:\Projects\Quietmirror\_support\cache\FreeCAD_1.1.4-Windows-x86_64-py311.7z (418088341 bytes).
- SHA-256 matched GitHub release asset digest: 4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d.
- PrusaSlicer official release: https://github.com/prusa3d/PrusaSlicer/releases/tag/version_2.9.6
- Package: https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.9.6/PrusaSlicer-2.9.6.zip
- Archive: E:\Projects\Quietmirror\_support\cache\PrusaSlicer-2.9.6.zip (106598059 bytes).
- SHA-256 matched GitHub release asset digest: 5aaf22e42f95accecfa122d23a835911f289ecc2ff606db3e83d637ddcc0a209.
- Raw release metadata: work\freecad_release.json and work\prusaslicer_release.json.

## Python dependencies

The versions resolved from PyPI match the repository's requirements.txt: cadquery 2.8.0; trimesh 5.1.1; numpy 2.5.4; scipy 1.18.1; rtree 1.4.1; networkx 3.7; shapely 2.2.0; pymeshlab 2025.7.post1; matplotlib 3.11.2; Pillow 12.3.0; lxml 6.1.3. CAD kernel: cadquery-ocp 7.9.3.1.1; VTK 9.6.2. Full freeze: work\requirements-resolved.txt.

Fresh imports of cadquery, trimesh, numpy, scipy, shapely, vtk, PIL, and pymeshlab all passed. Evidence: work\import_status.json. pip check returned "No broken requirements found."

## Portable runtime and game-friendly execution

Dot-source enter-project.ps1 before project commands. It now also sets FreeCAD data/config/temp to E:, MPLCONFIGDIR to E: cache, and limits OMP/OPENBLAS/MKL/NUMEXPR/VTK threads to 2; VTK SMP uses Sequential. For background compute, set the current PowerShell process PriorityClass to BelowNormal before launching children. Both added wrappers do so.

- Invoke-FreeCADCmd.ps1 automatically passes E: user.cfg and system.cfg.
- Invoke-PrusaSlicer.ps1 automatically passes --sw-renderer --datadir E:\Projects\Quietmirror\_support\config\PrusaSlicer --threads 2.

PrusaSlicer initially failed with exception 0xc00000fd in the installed NVIDIA OpenGL driver nvoglv64.dll, as confirmed by Windows Application Error event 1000. Its official --sw-renderer option loads the package's own mesa\opengl32.dll and fixes the startup failure. --help and a real CLI slice both returned exit code 0 with software rendering. No system DLLs or drivers were changed. The PrusaSlicer executable must be invoked with --sw-renderer on this system.

## Executed smoke verification

1. CadQuery produced a 10 x 10 x 10 mm solid, exported STEP and STL. Solid isValid=True; STL is watertight with consistent winding and volume 1000 mm3.
2. FreeCADCmd read the STEP, found one valid solid with volume 1000 mm3, and saved a native cube.FCStd. Its reported UserHomePath, UserAppData, AppTempPath, UserParameter and SystemParameter all point to E: project support folders. Exit 0.
3. PrusaSlicer with software rendering sliced the STL using two threads and PLA-like 0.4 mm nozzle/0.2 mm layer/210 C nozzle/60 C bed settings. Exit 0; produced work\environment_smoke\cube.gcode (161327 bytes). This is an environment test only, not a printer-specific user deliverable.

Evidence and smoke models: work\environment_smoke\cadquery_smoke.json, work\environment_smoke\freecad_smoke.json, cube.step, cube.stl, cube.FCStd, cube.gcode. Logs: work\prusa_smoke.txt and work\prusa_smoke_error.txt.

No GUI windows were opened and no restart was requested. Model source code was not changed by environment preparation.
