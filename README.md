# egospatial

**利用空间记忆和已执行动作历史，评测第一人称视觉模型的下一步移动 / 交互预测。**

本项目从 [EgoPlan](https://github.com/ChenYi99/EgoPlan) 的问题与当前观察帧、EPIC-KITCHENS 的真实视频及动作时间标注中构建任务轨迹。每轮输入若干任务前的空间参考帧、任务初始 anchor，以及已经执行的 GT 标签和观察，预测当前帧之后的一个动作。模型预测不会写回历史，因此这是 **GT replay 下的逐步预测评测**，不是自由执行或机器人闭环成功率。

当前协作数据是 **P30_111 一条视频**的最新冻结版本：27 个 EgoPlan 题目区间，494 个合并动作节点，**461 条可评分样本**（264 移动、197 交互），覆盖其中 26 个区间。33 个节点不评分：27 个截断 / 未标注尾段和 6 个需要重新标注的混合标签节点。它不是 461 条独立视频，也不是完整的 EgoPlan benchmark。

> 参考标签仍是研究草稿：移动标签主要来自二维光流候选；一小段经过 RGB 整理，题 2176 的 f2087→f2139 按人工反馈修正为 `right+forward`。没有把这些标签宣称为三维相机轨迹真值。长题目区间可能跨越多个子目标，交互合并和任务对齐仍需人工复核。

## 1. 项目里有什么

```text
src/egospatial/
  sources.py       下载 / 转换 EgoPlan 与 EPIC 元数据
  motion.py        视频 -> 5 Hz 背景仿射光流运动候选
  extraction.py    问题区间、动作边界、连续 interact 合并及人工修正
  dataset.py       数据读取、边界连续性和可评分节点检查
  protocol.py      空间记忆 + anchor + 已执行 GT 前缀 -> 无泄漏模型输入
  labels.py        31 个合法写法、JSON schema 和评分
  backends.py      Codex CLI / OpenAI Responses API 适配器
  evaluation.py    并发、重试、断点续跑、历史真实结果导入
  export.py        导出离线展示大屏与完整输入输出 JSONL
  package.py       校验清单和 ZIP 打包
  resources/       提示词模板与大屏 HTML
configs/           可移植配置示例，无账号、机器路径或密钥
docs/              数据契约、提取规则与评测说明
tests/             合成数据上的协议、恢复、评分、后端与展示测试
```

公开 Git 仓库只放代码、文档和合成测试。实际数据、视频、原始模型回复、模型权重、登录信息不进入 Git。协作者另行获得 `egospatial-p30-461.zip`，并遵守上游数据条款；代码的 MIT 许可不覆盖上游图片、视频和标注。

## 2. 安装

建议 Linux / macOS，Python 3.10–3.12。仅阅读结果不需要 Python、GPU、API Key 或模型权重。

```bash
git clone https://github.com/Kouyouyi/egospatial.git
cd egospatial
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev,media,download]"
pytest -q
```

重新抽帧 / 切片 / 提运动候选需要系统 `ffmpeg`、`ffprobe`。Ubuntu：`sudo apt-get install ffmpeg`；macOS：`brew install ffmpeg`。展示回归检查另需 Node.js。

本版视觉动作评测不依赖 DA3、CUDA、Llama-2、Qwen 权重或原版 EgoPlan 的模型环境。只有复现 EgoPlan 官方模型本身，才需依照其上游说明另配权重和环境。

## 3. 合作者最快复现方式：使用协作数据包

把单独提供的 ZIP 解压到仓库的 `data/`。解压后路径为：

```text
data/egospatial-p30/
  benchmark/dataset.json              冻结版本；494 个节点中 461 个 eligible
  benchmark/frames/frame_0000000900.jpg  503 张索引帧，其中 475 张为实际测试图片字节
  metadata/egoplan_P30_111.json         27 个 EgoPlan 原始题目
  metadata/epic_actions.json           P30_111 的 635 条 EPIC 动作记录
  metadata/motion_proposals.json      本次冻结的运动候选
  metadata/recipe.json                空间参考帧选择、整理段落与人工修正
  metadata/extraction-acceptance.json  新提取器与当前版本的逐字段一致性核验
  evaluation/cases/*.json             461 条真实请求、回复和评分
  evaluation/summary.json             汇总指标
  review/review.html                   双击打开的离线大屏
  review/images/                      按 SHA 去重的真实模型附件
  review/frames/                      人工查看的结束帧
  review/videos/                      26 段可评任务的完整视频
  review/requests/ + outputs/          原始模型请求与回复
  review/all-results.jsonl             461 条完整评测记录
  SHA256SUMS.json                      全包文件级校验
```

```bash
mkdir -p data
unzip /path/to/egospatial-p30-461.zip -d data
egospatial verify data/egospatial-p30
egospatial stats data/egospatial-p30/benchmark/dataset.json
```

直接打开 `data/egospatial-p30/review/review.html`。大屏只显示这一个最新版本，可按任务 / 移动或交互 / 对错筛选，逐条查看全部实际输入图、完整提示词、原始回复、正确标签、当前与结束帧，并播放完整任务片段。本轮结束帧只供人工核对，不曾输入模型。

如果浏览器限制本地视频，可在解压目录运行 `python -m http.server 8000 --bind 127.0.0.1`，访问 `http://127.0.0.1:8000/review/review.html`。不要把数据服务直接暴露到公网。

## 4. 从头准备哪些数据

| 资源 | 是否必需 | 获取方式 / 注意 |
|---|---|---|
| EgoPlan 验证问题标注 | 重新提取必需 | 上游发布的 `EgoPlan_validation.json`，或本项目下载命令获取固定 HF 镜像的 annotation parquet |
| EPIC-100 train + validation 动作标注 | 重新提取必需 | 自动从官方 annotation 仓库固定 commit 下载，并按 `video_id` 筛选 |
| EPIC-KITCHENS P30_111 原视频 | 重新抽帧、切片、光流必需 | 按 [EPIC 官方下载入口](https://epic-kitchens.github.io/2024#downloads) 与 [官方脚本](https://github.com/epic-kitchens/epic-kitchens-download-scripts)获取；只需这一条视频 |
| recipe + 冻结运动候选 | 精确重建本次 461 条必需 | 协作包的 `metadata/`，包括人为选择和修正，不应由下载脚本伪造 |
| 其他 EPIC 视频、EgoDex、DA3 或 Llama-2 权重 | 本版不需要 | 不用为了跑本 benchmark 下载整个数据集 |

P30_111 原视频约 5.58 GB（5.19 GiB），1920×1080、50 fps、92,013 帧、1840.26 秒，MD5：
`36ba7f1de0d4d533013e299e90eafa6a`。协作包包含抽帧与任务视频，不包含 5.58 GB 原视频。

本次 EgoPlan 来源是 [lmms-lab/EgoPlan 固定 revision](https://huggingface.co/datasets/lmms-lab/EgoPlan/tree/515f017faf0cdf42a25654a1bcd879c12277eff1)，全标注 3355 条，选出 P30_111 的 27 条。上游镜像后来的 main 版本数量有变化，精确复现不要静默切换。下载器只取 parquet 标注，不下载该镜像的全部视频 ZIP。下载标注可能需按镜像要求登录 / 授权；原视频遵守 EPIC 的访问要求。

```bash
mkdir -p data/sources
egospatial download-metadata --kind egoplan --output data/sources/EgoPlan_validation.json
egospatial download-metadata --kind epic --video P30_111 --output data/sources/epic_actions.json
```

EPIC annotation 固定 commit：
`ea8b40457a400c3fffa1c7f406ef3dc169cc2522`。下载器不代替用户接受上游协议。详见 [第三方来源与条款](THIRD_PARTY_NOTICES.md)。

## 5. 如何从 EgoPlan 提取本项目评测数据

这里的“EgoPlan 结果”指题目记录、观察帧位置与任务进度标注。**EgoPlan 模型预测的 A/B/C/D 不是本项目移动标签真值。** 若已有官方评测输出，可通过 `--egoplan-results` 按 `sample_id` 选择题目；不要从模型预测选项反推相机移动。为保持相邻题目边界，建议先用全量问题生成轨迹，再在评测阶段筛题。

1. 对一个 `video_id` 的问题按 `current_observation_frame` 排序。每个任务从本题当前帧到下题当前帧，最后一个到视频末尾。
2. 将 EPIC 动作原始零基结束索引换成“严格在操作结束后的观察帧”：`after_frame = stop_frame + 2`（本项目源视频帧号从 1 开始）。
3. 加入 5 Hz 二维运动候选的结束点；相同结束点合并为一个草稿节点。保留来源和质量标记。
4. 合并同一区间中相邻、连续、纯 `interact` 的操作；不跨移动、混合、未知尾段或题目边界。只保留段首输入和段末观察，原细步骤保存在 `source_steps`。
5. 应用 recipe 中显式整理和人工修正；保留人工来源。截断 / 未标注尾段和不合法组合不评测。
6. 为每个 eligible 节点生成一轮：空间记忆 + anchor + 已执行 GT 标签/结束观察 → 当前帧下一动作。

使用包中冻结候选重建（无需重新下载或解码视频）：

```bash
egospatial extract \
  --egoplan data/egospatial-p30/metadata/egoplan_P30_111.json \
  --epic data/egospatial-p30/metadata/epic_actions.json \
  --proposals data/egospatial-p30/metadata/motion_proposals.json \
  --recipe data/egospatial-p30/metadata/recipe.json \
  --output data/rebuilt/dataset.json
```

整理后的提取器会产生新的内容版本号，但全部 494 个节点的边界、动作、语义、可评标志、质量、目标文本和空间记忆与冻结版本一致，核验记录在数据包中。不要仅为沿用历史结果而手改新数据的版本号。

从原视频重新生成候选和媒体：

```bash
egospatial motion --video data/raw/P30_111.MP4 --output data/new-motion.json
egospatial media --dataset data/rebuilt/dataset.json --video data/raw/P30_111.MP4
```

完整命令与算法阈值见 [提取说明](docs/EXTRACTION.md)。重新解码 / JPEG 编码可能改变像素和候选；严格复现历史请求应直接使用包内实际图片，不能把新编码图片宣称为字节一致。

## 6. 标签、输入和评分

合法标签为六个方向 `forward backward left right up down`、`interact`，以及两个不同且非相反方向的组合。共有 **31 个字符串写法**（6+1+24），对应 **19 种方向集合**。不允许 `interact+方向`、三个方向、重复或相反方向。

```json
{"action_semantics":"向右转动并向前靠近冰箱","action_labels":["right+forward"]}
```

`action_labels` 恰好一个字符串，`right+forward` 与 `forward+right` 得分等价。`["right","forward"]` 不合法。动作语义仅供解释，评分只看方向集合；单独记录输出格式合法率。连续交互不拆成多个视觉重复的 `interact`。

第一轮：固定空间记忆 + anchor（同时是当前帧，仅一次）。
第 t 轮：固定空间记忆 + anchor + 前 t−1 个 GT 标签 / 新观察；最后一张是当前帧。不提供当前 GT 标签、当前步骤语义或动作结束图。所有过去观察完整保留，不暗中截短上下文；最长一轮有 94 张图片，模型需支持相应图像上下文。

报告 overall / navigation / interact 的匹配率、已完成数和有效输出。按节点 micro 平均；每个节点权重相同。失败请求单独报告、不当作已完成错误，也不能通过只保留成功子集宣称跑完。历史中某个节点需复核时，后续只提供“该历史区间标签待复核”和其观察，不伪造合法标签。

本次已完成的 GPT 结果（`gpt-6.2-sol`，reasoning high）：

| 分组 | 正确 / 总数 | 标签匹配率 |
|---|---:|---:|
| 全部 | 207 / 461 | 44.90% |
| 移动 | 34 / 264 | 12.88% |
| 交互 | 173 / 197 | 87.82% |

这是该草稿参考和 GT replay 协议的结果，不能解读为闭环任务成功率；历史模型名也不保证所有账号当前可调用。协议与字段见 [数据契约](docs/DATA.md) 和 [评测 pipeline](docs/EVALUATION.md)。

## 7. 自动化评测

API 方式使用 [OpenAI Responses 的图片输入](https://developers.openai.com/api/docs/guides/images-vision) 和 [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。Key 从环境变量读取，不写入配置或结果。

```bash
export OPENAI_API_KEY="YOUR_KEY"
egospatial evaluate \
  --dataset data/egospatial-p30/benchmark/dataset.json \
  --output runs/my-model --backend responses --model YOUR_VISION_MODEL \
  --question 2176 --workers 1
```

先完整测一条任务，再去掉 `--question` 测全部 461 条；按账户限流调整 `--workers`。对不支持 reasoning 参数的模型设 `--reasoning ""`。工具不自动替换模型、不输出自己猜测的参考答案。

Codex CLI 方式：在**数据所在机器**安装官方 CLI 并执行 `codex login`，然后：

```bash
egospatial evaluate \
  --dataset data/egospatial-p30/benchmark/dataset.json \
  --output runs/my-codex --backend codex --model YOUR_CODEX_VISION_MODEL \
  --question 2176 --workers 1
```

每轮独立临时目录、ephemeral 会话、忽略用户配置、只读沙箱、固定 JSON schema；若 CLI 事件表明使用了额外工具，本轮拒收。确认 CLI 版本支持相应参数。旧实验的本机 Codex ↔ 远端 SSH 私有桥接不随项目发布；合作者可以把协作包复制到其已登录 CLI 的机器，不需复刻某个人的端口、路径或登录配置。

相同命令可断点续跑；已完成且输入哈希相同的节点不重测。模型、prompt、数据版本或图片变更会拒绝混用结果，应换一个 run 目录。只对调用失败重试，预测错误不会为了提高分数而重试。

导出独立大屏（输出目录需为空，避免夹杂旧版本）：

```bash
egospatial export \
  --dataset data/egospatial-p30/benchmark/dataset.json \
  --run runs/my-model --clips data/egospatial-p30/review/videos \
  --output artifacts/my-model
```

也可编辑 [configs/pipeline.example.json](configs/pipeline.example.json)，将 `model` 改为自己的视觉模型，然后一键运行：

```bash
egospatial pipeline configs/pipeline.example.json
```

相对路径以配置文件所在目录为基准。默认使用已准备的媒体，不重新下载或重新提取数据。重复评测可续跑；重复导出需新空目录。

## 8. 维护与分享

```bash
pytest -q
node tests/review_smoke.cjs /path/to/review
egospatial package data/egospatial-p30 --output artifacts/egospatial-p30-461.zip
```

ZIP 自带 SHA-256 文件清单，命令也生成 ZIP 的 `.sha256`。数据包与公开仓库分开传给符合上游数据使用条件的合作者。不要提交 API Key、Codex 登录文件、完整数据和模型权重。

若修改标签 / 空间记忆 / 任务目标 / 图像，应保存新 dataset_version 和新的 run 输出目录。公开仓库中的示例测试全部使用合成图片，不把真实视频作为 CI 依赖。

代码：[MIT](LICENSE)。第三方数据：[来源与条款](THIRD_PARTY_NOTICES.md)。具体研究边界、未完成事项与协作建议见 [docs/EVALUATION.md](docs/EVALUATION.md)。
