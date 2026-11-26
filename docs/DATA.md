# 数据契约

一个 episode 对应一个相邻 EgoPlan 题目区间；一个 case 对应该区间内一个可评动作。
稳定索引使用 `episode_id + step_index`（历史 ID 保留 `_v1` 字样，不代表额外版本）。
视频帧号为 **一基索引**；50 fps 时源帧 n 的时间是 `(n-1)/50` 秒。

`dataset.json` 包含：
- `dataset_version, video_id, fps, frame_count`；
- `episodes[]`：`episode_id, question_id, next_question_id, original_question, goal`，
  `initial_frame, final_frame, clip, spatial_memory, steps`；
- memory 项：`id, description, frame.source_frame, frame.path`，必须早于任务开始；
- step 项：`before_frame, after_frame, action_semantics, action_labels`，
  `quality, source, completed, score_eligible`；
- 合并步骤的 `source_steps` 保留原细步骤；混合 / 三方向草稿保留
  `label_components`，标记 `taxonomy_status=requires_reannotation`，不评分。

没有历史帧截断策略：评测全部已执行前缀。即便过去节点本身不可评分，后面的当前帧
仍可使用其结束观察；非法 / 未知标签置空，并在提示中明确待复核。
最终未完成段不调用模型。

模型输出：
```json
{"action_semantics":"向右转并向前靠近目标","action_labels":["right+forward"]}
```
动作方向集合全匹配才正确，不计局部方向分。语义不评分；格式合法另记。
31 个拼写映射到 19 类语义动作，标签顺序不决定得分。

`evaluation/cases/<id>.json` 保存：
- 索引：`id, episode_id, question_id, step_index`；
- `request`：实际逻辑 messages、CLI prompt、图片源帧和 SHA、schema、输入哈希；
- `output`：原始 answer、模型、usage、时长、原始 API response / CLI events（新运行）；
- `reference` 和 `score`：独立于传给模型的请求。

大屏导出的 `samples/*.json` 再增加可移植媒体路径；对应 `.js` 使 file:// 下无需 fetch
也能逐条加载。所有图片与视频均在 review 目录内，不依赖个人机器上的绝对路径。
`all-results.jsonl` 每行一条完整 case，可按 case id 和 run_id 关联实际 request/output。

本次包保留冻结历史 dataset_version；重新提取产生新的内容版本号。边界相同不代表
可静默混用身份：要重用既有结果，必须明确验证任务、历史、prompt、图片字节及 schema。
