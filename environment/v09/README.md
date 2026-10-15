# V0.9 E 盘环境记录与脚本模板

当前项目位于 `E:\Projects\Quietmirror\github`，环境、工具、缓存及拓展位于相邻的 `E:\Projects\Quietmirror\_support`。本目录保存经过当前环境验证的启动脚本模板、依赖锁定记录与安装来源；大型工具和虚拟环境保留在 E 盘支持目录。

在当前机器继续工作时，先点源 `E:\Projects\Quietmirror\_support\enter-project.ps1`，再按交接报告运行生成与验证命令。`Open-FreeCAD-V09.cmd` 供用户手动查看原生文档；后台建模使用 `Invoke-FreeCADCmd.ps1`，切片使用 `Invoke-PrusaSlicer.ps1`。

新机器复现时，先将项目放到上述 E 盘路径，按 `ENVIRONMENT.md` 的官方来源、版本和 SHA256 准备便携 FreeCAD、PrusaSlicer 及 Python 环境，并将本目录四个启动脚本复制到 `E:\Projects\Quietmirror\_support` 后使用。脚本依赖其安装位置，不应直接从本模板目录执行。Python 顶层依赖见仓库 `requirements.txt`，当前完整解析版本见 `requirements-resolved.txt`。切片器使用软件渲染、两线程；打印前按实际打印机重切。

建模决策和当前进度见仓库 `reports/v09/HANDOFF.md`；打印 ZIP 中对应 `reports/HANDOFF.md`。FreeCAD 文档为命名 B-rep 与参数记录，修改几何应从参数化源代码重新生成。
