# Quietmirror · V0.9 PLA 三角骨架机械样机

前端为沿原曲面的1.6mm薄上键，下方固定侧裙、封闭前脸和USB支撑保留；前段和23×27mm键面保持，后肩收窄平滑。当前主体平面约58.70×90.09mm，冠高约26mm。普通壳壁名义1.6mm，平面三角筋1.8mm。上壳22、底架34个圆角三角减重轮廓，功能接口保留所需形状。

![实际模型](views/v09/01_isometric.png)

[修改前后](views/v09/07_before_after.png) · [俯视](views/v09/02_top.png) · [侧视](views/v09/03_left_side.png) · [底视](views/v09/04_bottom.png)

## 打印和编辑

- [完整打印包 ZIP 与发布记录](https://github.com/ht1580/Quietmirror-mouse/releases/tag/v0.9-pla)
- [20件PLA打印排版3MF](exports/v09/quietmirror_V0.9_PRINT_PLATE.3mf) · [分件STL/STEP](exports/v09/print/) · [配合校准件](exports/v09/calibration/)
- [FreeCAD原生文档](exports/v09/quietmirror_V0.9.FCStd) · [装配STEP](exports/v09/quietmirror_V0.9_MECHANICAL_ASSEMBLY.step) · [装配观察3MF](exports/v09/quietmirror_V0.9_VIEW_ONLY.3mf)
- [打印说明](reports/v09/PRINT_README.md) · [装配及限制](reports/v09/ASSEMBLY.md) · [交接报告与当前进度](reports/v09/HANDOFF.md)

打印使用PRINT_PLATE或print/，装配文件不能作为整块打印模型。通用0.4mm喷嘴/0.2mm层PLA实际切片估算50.21g、6h 15m 28s；必须选择自己的打印机配置重切。尚未实物试印、测力或疲劳验证。

## 已保存证据

[几何与孔型](reports/v09/design_checks.json) · [20件拓扑、静态、采样行程和装入路径](reports/v09/validation.json) · [FreeCAD保存重开](reports/v09/freecad_validation.json) · [实际PLA切片](reports/v09/slice_summary.json)

最终零件均为有效单实体、封闭且无网格自相交；五个活动组采样行程/装入路径、滚轮旋转包络和五脚共面通过。独立检查匹配34个底孔实际截面，验证22个顶孔开口和孔缘，主键198点贴合母曲面、后背177点连续下降。采样结果不等于全局强度或连续运动证明。

## 源码与E盘环境

[参数](cad/parameters_v09.json) · [生成器](cad/build_v09.py) · [曲面与骨架](cad/geometry_v09.py) · [滚轮机构](cad/mechanisms_v09.py) · [官方参考记录](references/V0.9_REFERENCE_NOTES.md)

E盘环境入口：`E:\Projects\Quietmirror\_support\enter-project.ps1`。所有新增依赖、缓存、工具和拓展继续留在E盘。FreeCAD文件包含命名B-rep及参数记录，不伪称已恢复CadQuery历史树或求解装配关节。

[上一版首页](README_V0.8.md) · [历史](HISTORY.md) · [许可证](LICENSE) · [署名](NOTICE.md)。V0.1–V0.8的模型与代码保留。
