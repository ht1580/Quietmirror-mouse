# 所有版本与下载

本仓库同时保留 **V0.1、V0.2、V0.3、V0.4、V0.5、V0.6、V0.7、V0.8** 的模型、可编辑源码、参数、视图、切片配置和验证报告。V0.8 没有覆盖旧模型。GitHub 文件页的 **Download raw file** 可以下载原文件。

**[一次下载整个项目 ZIP，包含全部历史版本](https://github.com/Quietmirror/github/archive/refs/heads/main.zip)**

![五版实际模型](views/history_V0.1-V0.5.png)

| 版本 | 设计变化 | 一体试握 STL | STEP | 3MF | 当版说明与源码 |
|---|---|---|---|---|---|
| V0.1 | 指部接触面与开放骨架的第一版试握件 | [STL](exports/quietmirror_fingertip_V0.1.stl) | [STEP](exports/quietmirror_fingertip_V0.1.step) | [3MF](exports/quietmirror_fingertip_V0.1_PRINT.3mf) | [说明](README_V0.1.md) · [源码](cad/build_mouse.py) · [参数](cad/parameters.json) |
| V0.2 | 游狼短机身方向，连续侧壳与完整尾壳 | [STL](exports/v02/quietmirror_fingertip_V0.2.stl) | [STEP](exports/v02/quietmirror_fingertip_V0.2.step) | [3MF](exports/v02/quietmirror_fingertip_V0.2_PRINT.3mf) | [说明](README_V0.2.md) · [源码](cad/build_v02.py) · [参数](cad/parameters_v02.json) |
| V0.3 | 侧面平顺化，10个后壳孔，侧键窗口及独立键帽 | [FIT STL](exports/v03/quietmirror_fingertip_V0.3_FIT.stl) | [FIT STEP](exports/v03/quietmirror_fingertip_V0.3_FIT.step) | [3MF](exports/v03/quietmirror_fingertip_V0.3_PRINT.3mf) | [说明](README_V0.3.md) · [源码](cad/build_v03.py) · [参数](cad/parameters_v03.json) |
| **V0.4** | **Fenrir外形方向；低前端、后移壳背、6个较大后壳窗口；V0.3底部不变** | **[FIT STL](exports/v04/quietmirror_fingertip_V0.4_FIT.stl)** | **[FIT STEP](exports/v04/quietmirror_fingertip_V0.4_FIT.step)** | **[3MF](exports/v04/quietmirror_fingertip_V0.4_PRINT.3mf)** | [归档说明](README_V0.4.md) · [源码](cad/build_v04.py) · [参数](cad/parameters_v04.json) |
| **V0.5** | **后壳6→10孔；2.2 mm细筋；逐孔随轮廓收形，3—4—3镜像；底部不变** | **[FIT STL](exports/v05/quietmirror_fingertip_V0.5_FIT.stl)** | **[FIT STEP](exports/v05/quietmirror_fingertip_V0.5_FIT.step)** | **[3MF](exports/v05/quietmirror_fingertip_V0.5_PRINT.3mf)** | [归档说明](README_V0.5.md) · [源码](cad/build_v05.py) · [孔形源码](cad/vent_layout_v05.py) · [参数](cad/parameters_v05.json) |
| **V0.6** | **除侧键外镜像；取消外伸底边；12孔与窄外围筋；增加充电/开关口和两种主板示意** | **[FIT STL](exports/v06/quietmirror_fingertip_V0.6_FIT.stl)** | **[FIT STEP](exports/v06/quietmirror_fingertip_V0.6_FIT.step)** | **[3MF](exports/v06/quietmirror_fingertip_V0.6_PRINT.3mf)** | [归档说明](README_V0.6.md) · [源码](cad/build_v06.py) · [参数](cad/parameters_v06.json) · [电子参数](cad/electronics_v06.json) |

## 独立侧键及开孔壳体

| 版本 | 壳体 STL / STEP | 前侧键 STL / STEP | 后侧键 STL / STEP | 装配位置 STEP |
|---|---|---|---|---|
| V0.3 | [STL](exports/v03/quietmirror_fingertip_V0.3_SHELL.stl) / [STEP](exports/v03/quietmirror_fingertip_V0.3_SHELL.step) | [STL](exports/v03/side_button_1_V0.3_PRINT.stl) / [STEP](exports/v03/side_button_1_V0.3_PRINT.step) | [STL](exports/v03/side_button_2_V0.3_PRINT.stl) / [STEP](exports/v03/side_button_2_V0.3_PRINT.step) | [3件装配](exports/v03/side_button_assembly_V0.3.step) |
| V0.4 | [STL](exports/v04/quietmirror_fingertip_V0.4_SHELL.stl) / [STEP](exports/v04/quietmirror_fingertip_V0.4_SHELL.step) | [STL](exports/v04/side_button_1_V0.4_PRINT.stl) / [STEP](exports/v04/side_button_1_V0.4_PRINT.step) | [STL](exports/v04/side_button_2_V0.4_PRINT.stl) / [STEP](exports/v04/side_button_2_V0.4_PRINT.step) | [3件装配](exports/v04/side_button_assembly_V0.4.step) |
| V0.5 | [STL](exports/v05/quietmirror_fingertip_V0.5_SHELL.stl) / [STEP](exports/v05/quietmirror_fingertip_V0.5_SHELL.step) | [STL](exports/v05/side_button_1_V0.5_PRINT.stl) / [STEP](exports/v05/side_button_1_V0.5_PRINT.step) | [STL](exports/v05/side_button_2_V0.5_PRINT.stl) / [STEP](exports/v05/side_button_2_V0.5_PRINT.step) | [3件装配](exports/v05/side_button_assembly_V0.5.step) |

V0.4沿用V0.3键帽的名义几何和打印朝向，前/后键安装高度分别降低2.7/0.4 mm。V0.5保留V0.4侧键部件及位置，仅改变后壳孔阵。每版仍保留独立文件以便下载、比较和未来修改；独立键帽目前只有配合/触达验证，没有弹性回位和真实点击机构。

## 设计报告与证据目录

| 版本 | 设计与验证 | 打印说明 | 视图 | 电子估计包络 |
|---|---|---|---|---|
| V0.1 | [reports](reports/) | [打印](slicing/README.md) | [views](views/) | [STEP](exports/electronic_envelopes_ESTIMATES.step) |
| V0.2 | [reports/v02](reports/v02/) | [打印](slicing/V0.2_PRINTING.md) | [views/v02](views/v02/) | [STEP](exports/v02/electronic_envelopes_V0.2_ESTIMATES.step) |
| V0.3 | [reports/v03](reports/v03/) | [打印](slicing/V0.3_PRINTING.md) | [views/v03](views/v03/) | [STEP](exports/v03/electronic_envelopes_V0.3_ESTIMATES.step) |
| V0.4 | [reports/v04](reports/v04/) | [打印](slicing/V0.4_PRINTING.md) | [views/v04](views/v04/) | [STEP](exports/v04/electronic_envelopes_V0.4_ESTIMATES.step) |
| V0.5 | [reports/v05](reports/v05/) | [打印](slicing/V0.5_PRINTING.md) | [views/v05](views/v05/) | [STEP](exports/v05/electronic_envelopes_V0.5_ESTIMATES.step) |

这些是设计迭代版本，不是已完成实物验证的产品型号。所有尺寸均按毫米建模，导入100%比例。使用真实打印机配置；仓库不发布可直接发往未知打印机的G-code。

完整提交历史见 [GitHub commits](https://github.com/Quietmirror/github/commits/main/)。版本专用源文件和参数保留在当前目录；共享帮助脚本支持选择旧版本。如需精确复现当时整个工具链文件状态，可从提交历史切换到对应版本提交。

V0.5保留性检查：[历史文件对比](reports/v05/history_preservation.json)。V0.4的历史切片配置和结果保持原样；新旧版本在V0.5同一配置下的额外对比仅存入[本轮报告](reports/v05/comparison_slice.json)。

## V0.6 三版与历史保留

V0.6 按新要求重新设计对称底部，旧版的“底部不变”约束只适用于各自历史版本。

[纯试握](exports/v06/quietmirror_fingertip_V0.6_FIT.step) · [ATK A1 Plus 示意](exports/v06/quietmirror_V0.6_ATK_A1_PLUS_ESTIMATED.step) · [PAW3950 示意](exports/v06/quietmirror_V0.6_PAW3950_CUSTOM_ESTIMATED.step) · [完整报告](reports/v06/DESIGN.md) · [打印说明](slicing/V0.6_PRINTING.md) · [所有新视图](views/v06/) · [历史文件核对](reports/v06/history_preservation.json)。

新电子模型均为估计布局；V0.1–V0.5 的模型、参数、专用源码、图和报告保留原文件。共享工具只追加兼容新版本的选项。

## V0.7 活动试按套件

缩小左右主键、增加镜像前孔，细长双侧键；20 个塑料件组成五键及滚轮机械试按套件。V0.6 的 Z≤5.4 mm 底部保留。另附两种电子空间示意，并明确标出未解决冲突。

[归档说明](README_V0.7.md) · [分件 STL/STEP](exports/v07/print/) · [打印 3MF](exports/v07/quietmirror_V0.7_PRINT_PLATE.3mf) · [机械装配 STEP](exports/v07/quietmirror_V0.7_MECHANICAL_ASSEMBLY.step) · [ATK 示意](exports/v07/quietmirror_V0.7_ATK_A1_PLUS_ESTIMATED.step) · [PAW3950 示意](exports/v07/quietmirror_V0.7_PAW3950_CUSTOM_ESTIMATED.step) · [所有视图](views/v07/) · [历史核对](reports/v07/history_preservation.json)。

V0.7 是机械试按设计，不是实物验证完成的产品；旧版固定触感件的说明仍按各自历史范围理解。

## V0.8 平顺侧键与前端开放

主键恢复23 mm原宽并保持27 mm短长度，前沿框架退开；侧键前移3 mm并贴随侧壳曲面，底框局部收边。修正内部让位，并按静止、按压、转动和顺序装入进行检查。电子示意单独替换11个试按夹具，最终安装接口待设计。

[当前说明](README.md) · [分件 STL/STEP](exports/v08/print/) · [打印 3MF](exports/v08/quietmirror_V0.8_PRINT_PLATE.3mf) · [机械 STEP](exports/v08/quietmirror_V0.8_MECHANICAL_ASSEMBLY.step) · [ATK 示意](exports/v08/quietmirror_V0.8_ATK_A1_PLUS_ESTIMATED.step) · [PAW3950 示意](exports/v08/quietmirror_V0.8_PAW3950_CUSTOM_ESTIMATED.step) · [所有视图](views/v08/) · [历史核对](reports/v08/history_preservation.json)。


## V0.9 · PLA 三角骨架与光顺前端

保留原前段、纵坡与23×27主键，后肩按最新反馈收窄；26mm冠、1.6mm薄上键、1.8mm三角筋。固定下裙、前脸封口及USB支撑，后部边界适配三角减重，实际孔数见本轮报告，功能开口例外。外部侧键带下降2.8mm，后侧内部机构另降0.8mm，滚轮轴14.3mm、1.3mm轴承耳径向壁和2.4mm转折支架。导出20件STL/STEP、FreeCAD和PLA3MF；保存几何、网格、机构及切片证据，未实物打印。旧版不覆盖。
