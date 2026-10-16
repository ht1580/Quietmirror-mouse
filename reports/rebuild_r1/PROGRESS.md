# R1 工作快照：未验收，不作为可直接打印成品

这次重建取代此前的设计方向；旧 V0.9 文件和发布保留用于追溯。原上游 V0.9 与我们旧 V0.9、新 R1 是三个不同版本。

## 用户确认的目标

- 基于 G-Wolves Fenrir Pro 网络多视图及类似开源工程推导独立外形；不要求假称取得原厂 CAD。
- 五个脚贴点 **直径 8 mm**，其余底部开放。
- 上壳大尺度镂空与实心独立左右键优先参考 MiniSE。
- 开关、螺丝、USB-C、侧键、传感器预留和脚贴的功能尺寸固定；必要时只调整外形及布局。
- 使用 Omron D2F、Alps EC10E、USB-C 和通用传感器预留；电子板后续适配。
- 输出冲突、结构验证证据、安装图、PLA 文件及可供继续修改的报告。

## 已完成并有证据

1. 下载原上游 `65d2ee671d70bcb294c66902392cb64b8058e74f` 并独立审计；见 [审计报告](upstream_v09/UPSTREAM_V09_AUDIT.md)。原版约90.264×61.971×26.002 mm，存在底框，主键以V3/V4为主，不满足新目标。
2. 独立张量积 BSpline 母面：名义81.7×61.2×28.3 mm。来源为公开官方多视图，不含受限扫描。官方文字61.2mm宽与其图60.2mm宽的矛盾保留说明。
3. 母面顶视轮廓 IoU≈0.975、Z≥5mm侧视IoU≈0.949；这是图片对照，不是制造精度或总体符合率。图片线宽不确定约0.55mm；尾唇因PLA壁厚抬高。
4. 首个集成 BODY 已生成且为有效单实体。整0–5mm低带减五脚允许柱的体积为0，五脚截面直径8mm。见 `requirements_geometry.json`（绑定本轮集成模型，后续修模后需重跑）。
5. 真实 Gmsh/CalculiX 梁基准通过，细网格弯曲解析误差约1.12%。**这不是主壳强度通过。**
6. 六种运动打印件初版、硬件参考、USB插头/传感器量规和实际CAD预览已生成。

## 正在修复 / 未完成

- D2F真实偏置作动点、倾斜安装座、保持方式及全行程冲突仍在迭代。
- 主键与固定支座、滚轮载架的局部静态/运动冲突尚未最终消除。
- 部分初版STL有数值缝边/零面积面；正在采用绝对弦差重新网格化并独立检查自交。不得把有效STEP当成可直接打印STL的证明。
- USB插头31姿态、传感器光路、真实孔量规及完整装入路径尚未最终通过。
- 实际主壳多档有限元、收敛与反力检查尚未完成。不能声称PLA强度、疲劳或实物手感已验证。
- 最终原生FreeCAD、带配置3MF、切片验证和最终安装图待模型冻结后重新生成。

## 快照使用边界

本提交是可恢复工作进度。`cad/rebuild_r1` 源码可能已经包含比 `exports/rebuild_r1` 更晚的修复；必须重新运行 `build.py` 才能同步。当前预览和导出不是验收版本，**请勿据此直接制造或购买全部零件**。最终报告会以输入SHA256绑定模型、验证和预览。

全部工作、工具、缓存和文件保存在 E 盘；已有 FreeCAD、Gmsh、CalculiX、CadQuery、PrusaSlicer 继续复用。后续从 `cad/rebuild_r1/parameters.json` 与生成器继续，不修改历史版本。

## 公开参考

- [Fenrir Pro 官方](https://shop.g-wolves.com/products/g-wolves-fenrir-pro-8k-wireless-mouse)：外形与名义尺寸。
- [Razer MiniSE 官方](https://www.razer.com/gaming-mice/razer-viper-mini-signature-edition)：主键分区与大尺度三角/梯形外骨骼。
- [olliebella](https://github.com/badjeff/olliebella)：小型分离传感器/编码器板、可调传感器位置和独立机械装配思路；未复制其CAD或声称通用光学高度。
- [Kotinos](https://github.com/pseudoku/Kotinos)：开放支架与分模块装配参考；未复制其CAD/SCAD或供体孔位。
- [GCT USB4105](https://gct.co/connector/usb4105)：接口包络参考；通用适配板不是已验证现货电路。
