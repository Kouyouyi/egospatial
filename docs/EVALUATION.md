# 自动评测、验收与协作

## 每轮协议

1. 从私有 dataset 中取得任务、记忆和已执行前缀；
2. 编译器只生成公共 request，不把当前参考动作或 after_frame 图带入 payload；
3. backend 只收到 request 与对应图片；评分器在模型返回后才读取当前参考；
4. 完整保存实际请求 / 图片哈希、原始模型回复、格式与动作得分；
5. 下一轮固定追加 GT 及新观察，不使用模型预测；每轮为独立请求；
6. 非完整 / 需复核节点不发模型请求，保留其来源以便标注。

这评测的是“给定正确历史之后，预测下一动作”的能力。它不验证执行可行性、到达
成功、自由路线规划、未知物体搜索成功率，也未单独给任务文本中的对象推断打分。
下一题目标和其文字答案可用于定义外部给定的过渡目标，不作为“预测下一子任务”
的隐藏答案再评分。部分长区间的目标可能与实际后续动作不完全对齐，需要改进。

## 重试和恢复

整批配置绑定数据内容、版本、模型、reasoning、prompt、schema；每 case 绑定逻辑
消息和图片字节哈希。成功节点不会重跑，错误预测也不重试。调用异常最多重试指定
次数；失败保留 failed，后续同命令可再尝试。批次文件锁防止两个进程覆盖。

输出目录不可混用模型 / protocol。case 文件原子写入。同一机器多 worker 可并发，
默认1；不要未经账号限流测试就把并发开大。报告 expected/completed/failed 以及
三个动作分组的准确率，不因有失败而宣称全量完成。

历史461条通过 import-results 显式导入：逐条核对 messages、图片SHA、源帧、
输出schema、input_mode，重算得分。保留历史原始 prompt 和 outputs，不用新模板
假装它们来自新一次调用。新 CLI prompt 的附件编号表达与历史桥接包装略有不同；
逻辑 multimodal messages 完全一致，但不声称两个 wrapper 文本逐字相同。

## 验证命令

```bash
pytest -q
node tests/review_smoke.cjs data/egospatial-p30/review
egospatial verify data/egospatial-p30
```

测试覆盖：禁止当前答案和未来图泄漏、任务前记忆保留、首轮 anchor 不重复、历史
只使用 GT 前缀、无效 / 截断节点不调模型、对称组合评分、断点续跑和输入变更拒绝、
模型 adapter 的图片顺序与 schema、离线大屏全部 case 可访问和实际图片存在。

重建新大屏：
```bash
egospatial export --dataset data/egospatial-p30/benchmark/dataset.json \
 --run data/egospatial-p30/evaluation \
 --clips data/egospatial-p30/review/videos --output artifacts/imported-review
```

## 合作前建议复核的内容

当前代码是可执行的研究原型，单视频参考仍需审标。优先检查：
光流漏检或方向混淆、过长 interact 合并、next-question 目标与区间是否匹配、
物体当前状态与历史空间参考的差异。没有自动认定“所有461条都是最终人工GT”。

修改标注后创建新版本及新 run，再报告其指标。公开仓库不包含私有连接器密钥或
个人 SSH 配置；在合作者自己的环境设置标准环境变量和模型登录即可。
