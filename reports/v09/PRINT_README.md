# Quietmirror V0.9 · PLA 打印包

本轮保持原前段轮廓、纵向角度与 23 × 27 mm 左右键接触面，按最新标注收窄后肩；实际主体 X×Y×Z 约 58.696 × 90.094 × 26.002 mm。

## 修改

- 左右键由母壳外表面向内法向增厚 1.6 mm，只让薄上键活动；下方侧裙、封闭前脸及充电口支撑归固定 BODY，纵向角度保持。
- 收回前端两侧肩翼；后肩收窄，后背连续平滑；后部边界三角再剖分使减重孔靠近约 2 mm 外缘筋。
- 冠高约 28 → 26 mm；普通壳壁名义 1.8 → 1.6 mm；平面筋目标 2.2 → 1.8 mm。
- 上壳 22、底架 34 个圆角三角减重轮廓；滚轮、传感器、开关、螺钉等功能接口保留工作所需形状。孔轮廓数与最终独立开口数的核验见 reports/design_checks.json。
- 保留五脚位置、传感器接口、五键可拆机械试按机构及可旋转/下压滚轮；V0.1–V0.8 未改动。

## 使用哪些文件

- `quietmirror_V0.9_PRINT_PLATE.3mf`：20 件分开排版，内含通用 PLA 切片设置。
- `print/`：20 个按打印朝向放置的 STL 和 STEP，底部为 Z=0。
- `calibration/`：先打印配合间隙、柱塞和轮轴校准件。
- `quietmirror_V0.9.FCStd`：FreeCAD 原生文档，20 个命名 B-rep 零件和参数记录；不是自动恢复的 CadQuery 历史树或已求解装配关节。
- `quietmirror_V0.9_MECHANICAL_ASSEMBLY.step`：装配观察 STEP，含 5 枚非打印开关示例，不能整块直接打印。
- `quietmirror_V0.9_VIEW_ONLY.3mf`：装配观察 3MF，不能替代分件打印排版。
- `source/`：本轮及依赖的参数化生成/验证源代码。完整工作仓库仍在 E:\Projects\Quietmirror\github。
- `views/07_before_after.png`：从真实 STL 渲染的修改前后对照。
- reports/HANDOFF.md：最新要求、当前进度、结构决策和继续修改命令；reports/TASK_STATUS.json 提供机器可读进度。

## PLA 设置与实际切片

假设 0.4 mm 喷嘴、1.75 mm PLA、0.2 mm 层高、4 壁、20% gyroid、210°C/60°C、可清理支撑；配置随 3MF 保存。请在切片器选择自己的打印机和实际 PLA 参数后重切；包中不提供可直接发送未知打印机的 G-code。

本版 20 个塑料件 CAD 体积约 24.473 cm³。通用配置实际切片估算：模型 30.46 g，支撑 18.89 g，合计 50.21 g，时间 6h 15m 28s。这不是你的打印机的保证工时。

BODY 五脚朝下；键面朝上；滚轮侧面平放、轴孔朝上；小零件按 print/ 朝向。先试印校准件，再检查 0.3 mm 名义导向间隙和 Ø3 mm 轴的配合。

## 验证边界

保存的 CAD/STL、机构静态与采样行程、轮旋转包络、安装路径、足底共面、三角孔、母壳键面与通用 PLA 切片已经计算核验，完整证据在 reports/。尚未实物打印、试握、测力或验证疲劳寿命。0.8 mm PLA 段落弹片为试验件，需实物调整；五个真实开关、螺钉和脚贴另备。原项目电子功能仍未实现/实测。

## E 盘工具

FreeCAD: E:\Projects\Quietmirror\_support\tools\FreeCAD\bin\FreeCAD.exe

环境入口: E:\Projects\Quietmirror\_support\enter-project.ps1

后续支持、依赖、缓存和拓展继续保存在 E 盘项目目录。
