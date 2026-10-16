# Fenrir Pro / MiniSE 参考与来源核对

研究日期：2026-10-15。此目录为证据参考，不是鼠标原厂 CAD，也未包含有禁止再分发限制的第三方扫描。

## 产品身份与尺寸

用户所写“游狼 fennir pro”应对应 **G-Wolves Fenrir Pro 8K**。不要误用 WLMOUSE、Fenrir Asym 或 Fenrir Max。

| 证据 | 长 × 宽 × 高 / mm | 备注 |
|---|---|---|
| [G-Wolves 官方产品页](https://shop.g-wolves.com/products/g-wolves-fenrir-pro-8k-wireless-mouse) | 81.7 × 61.2 × 28.3 | 当前文字规格；紧凑对称指握形状，5 键、USB-C；名义外形尺寸可作为新设计初始约束。 |
| 官方产品页自身上传的 EloShapes 轮廓图 `fenrir_official_25.png` | 81.7 × 60.2 × 28.3 | 图中宽度与当前官方文字相差 1 mm；图中质量也与文字不一致。不要把此图当原厂 CAD 或忽略差异。 |
| [FindMyMouse 自采扫描页](https://findmymouse.com/mouse/g-wolves-fenrir-pro-8k) | 81.6 × 60.1 × 27.2 | 扫描测量值，区别于官方名义尺寸；只用于确认存在真实扫描与版本身份，未下载扫描或提取其几何。 |
| [Razer 官方支持页](https://mysupport.razer.com/app/answers/detail/a_id/9682) | 119 × 62 × 39 | Viper Mini Signature Edition，仅作为主键及镂空语言参考，不应让新壳被直接放大为此尺寸。 |

## Fenrir Pro 外形证据

已从 G-Wolves 官方产品 JSON 获取 5 张直接图片，并按原样保存。产品 JSON：

[官方产品 JSON](https://shop.g-wolves.com/products/g-wolves-fenrir-pro-8k-wireless-mouse.json)

| 文件 | 直接来源 | 内容 |
|---|---|---|
| `fenrir_official_01.png` | https://cdn.shopify.com/s/files/1/0540/7981/5877/files/1-01_edb7c3b2-45c3-41f5-abd6-ebcaf92076fa.png?v=1759934416 | 顶视，蜂窝主键、短宽外廓、左右对称。 |
| `fenrir_official_02.png` | https://cdn.shopify.com/s/files/1/0540/7981/5877/files/1-02_7bbb97ff-8ebc-4c8c-a057-ffcc0c7ea3c6.png?v=1759934416 | 左侧，双侧键、极低前端、后移背峰和快速下降的尾部。 |
| `fenrir_official_03.png` | https://cdn.shopify.com/s/files/1/0540/7981/5877/files/1-03_a221ab27-78fd-4db7-a46f-9330fba377ca.png?v=1759934416 | 右侧，无左侧双键凸出。 |
| `fenrir_official_04.png` | https://cdn.shopify.com/s/files/1/0540/7981/5877/files/1-04_b9e07bf8-6f03-4dd2-83f6-cc19dac463e2.png?v=1759934416 | 前上斜视，主键与侧壁衔接。 |
| `fenrir_official_25.png` | https://cdn.shopify.com/s/files/1/0540/7981/5877/files/20250831230412_1528_13.png?v=1766749378 | 官网展示的 EloShapes 顶/侧轮廓尺寸图；宽度有上述冲突。 |

图片观察属于定性证据。照片透视、边缘、低前端和背峰位置不能当作经过计量校准的完整曲面；没有 PCB、螺柱、传感器镜头、编码器的装配尺寸。新模型若依此重建，名称应为“参考 Fenrir Pro 的独立参数化重建”，不应称“原厂 Fenrir Pro 模型”。

## MiniSE 高权重特征

来自 [Razer 产品页](https://www.razer.com/gaming-mice/razer-viper-mini-signature-edition) 的三张直接官方图片，已在此目录保存：

| 文件 | 来源 |
|---|---|
| `minise_official_hero.webp` | https://assets2.razerzone.com/images/pnx.assets/9a858042c19e2d15bcab1dec9578212f/razer-viper-mini-se-black-hero-desktop.webp |
| `minise_official_chassis.webp` | https://assets2.razerzone.com/images/pnx.assets/bc378be1de3b6f05fc596ae33671b6fe/razer-viper-mini-se-white-magnesium-alloy-chassis.webp |
| `minise_official_weight_reduction.webp` | https://assets2.razerzone.com/images/pnx.assets/bc378be1de3b6f05fc596ae33671b6fe/razer-viper-mini-se-white-superior-weight-reduction.webp |

新方案应优先体现：

1. 左右分离的实心薄主键与轻微内凹触面；主键接触区不打蜂窝孔；中央窄滚轮通道。
2. 主键根部两侧三角开口；后背采用大尺度、有受力路径的外骨骼筋，而非密集均匀小孔。
3. 顶视中央倒三角、相邻三角开口与后缘大梯形/圆角四边开口的组合。MiniSE 并非所有开口都严格三角形；不能宣称任意三角网格都已精确复刻其布局。
4. 保留拇指握持区域和侧键支承。左右主键、侧键必须有独立限位及承载结构；外观图片不能证明这些机构尺寸。

Razer 使用镁合金。PLA 弹性、层间强度、最小筋宽、循环疲劳不能从镁壳外观推出，需按新零件自身几何与打印方向验证。

[Razer 官方安装/布局手册 PDF](https://dl.razerzone.com/master-guides/RazerSynapse3/VIPERMINISIGNATUREEDITION-000000158-en.pdf) 明确左右主键、滚轮、左侧两键、USB-C、脚贴、传感器的功能布局。该手册不提供可移植到新壳的内部尺寸。

## 可取得 CAD / 扫描与发布边界

本次已检索 G-Wolves 官方产品页面及公开网页的 Fenrir Pro + CAD/STEP/STP/STL/3D/scan/shape tester，未找到能证实是该 **Pro 版本** 且允许此次发布派生模型的原厂 CAD 或公开扫描下载。

FindMyMouse 是自采扫描的第一方提供者，但其同一页面内的服务条款将扫描下载设为付费账号权益；仅许可个人、非商业修改和打印，禁止发布、再分发源文件或派生数据。未经额外书面授权，不把其模型或派生几何加入可上传 GitHub 的设计。未付费、未绕过登录或下载限制。

公开搜索出现的 Cults H-VIX 是 **Fenrir Asym 外形的付费改装壳**，不是 Fenrir Pro，不应替代用户指定基模。未购买或下载。

此目录的品牌产品图片仅用于本地参考与溯源。公开/再分发报告优先列出来源链接，独立设计的最终预览与安装图由实际生成的 CAD 渲染。任何第三方资产都不应自动套用本项目代码许可证。

## 对“符合程度”和“可信性”的判断边界

- 有官方名义尺寸和定性轮廓依据，可以报告名义尺寸约束、归一化轮廓对照、独立模型的实际尺寸及差异。
- 没有合法原厂基模或实测扫描，不能报告外形完全一致、原厂安装孔完全匹配或 Fenrir Pro PCB 已适配。
- 若使用项目自建按钮机构，可以验证其静态/按压/安装路径不干涉、轴径间隙、限位、模型拓扑与打印条件，安装图应对应这些自建实际零件。
- “底部除五脚贴全镂空”若严格解释为五个悬空孤岛且不允许任何连筋，将无法形成单件可受力结构。应将脚贴台支承连接到侧壁/上层结构，同时明确底面镂空和上层必要支承的区别；不得偷偷恢复整片底板。
