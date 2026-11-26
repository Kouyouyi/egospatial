# 提取过程与复现边界

输入是 EgoPlan 原问题 JSON、EPIC 动作列表、motion-proposals.json 和 recipe.json。
原版 EgoPlan 的模型选项预测不能生成导航真值；可选 result JSON 只按 sample_id 关联。

## 帧与动作边界

每个问题从其 current_observation_frame 到下一个问题的 current_observation_frame。
EPIC 动作取 stop_frame+2 为结束后的观察源帧。任务区间中的事件结束点与运动结束点
共同形成有序边界，相同结束点合并。尾部没有完整动作结束依据时保留未完成节点，
不为补满区间编造答案。

连续纯 interact 按最大相邻区间合并，不能跨越移动、混合、未知或题目边界。合并段
保留第一个 before_frame、最后一个 after_frame 和全部 source_steps；任一细步骤
不完整，则整个合并段不评分。交互摘要按源叙述顺序连接，少量片段使用人工摘要。
目前自动合并不做额外视角稳定性审核，因此仍需人工复查是否漏掉视角变化。

## 运动候选算法

motion.py 对原视频每 10 帧采样（50 fps 时为 5 Hz），缩到 256×144 灰度：
- 屏蔽最下方区域，特征掩码为 y=8..72%H、x=8..W−8；
- Shi-Tomasi 最多 150 点，quality=0.01、minDistance=8；
- LK 光流 window=21×21、maxLevel=3，过滤误差>=25的点；
- 用 RANSAC 部分仿射拟合，阈值2像素，inlier ratio至少0.6；
- 背景横向位移超过2.5%W，反向映射为 left/right；
- 背景纵向位移超过2.5%H，映射为 up/down；
- 尺度变化绝对值>2.5% 且横纵位移<4% 时提 forward/backward；
- 相同候选方向连续至少20源帧才保留。

手部、物体运动、视差、镜头旋转都会影响这些候选。没有用 DA3 三维相机轨迹做 GT，
不要将缩放估计等同精确前进距离。fresh 光流可能因 OpenCV / 解码版本变化而变化，
精确重现使用协作包中冻结的候选与 recipe。

## recipe 的责任

memory_slots 是人工选出的覆盖厨房布局的候选帧，每个 episode 从各 slot 中选最大
且早于 anchor 的源帧。episode_overrides 是已整理的局部轨迹，corrections 是显式
人工改标。没有 recipe 时应重新标注这些决策，而不是声称从 EgoPlan 自动推导出来。

本次 extraction-acceptance 核对 27 episodes、494 nodes 和全部461可评样本的：
目标、初末帧、空间记忆、每节点起止帧、语义、标签、completed、eligible、quality。
新 extractor 的元数据 schema / 内容 hash 可以改变，所以不伪造旧版本号。
