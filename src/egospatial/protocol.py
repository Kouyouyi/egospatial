"""Compile only fixed memories, anchor and the already executed GT prefix."""
from importlib.resources import files
from .dataset import frame
from .labels import LABELS, schema
from .io import digest, sha
import json

SYSTEM = ("你是第一人称下一步骤预测器。先看固定空间记忆，再看任务anchor、已执行GT标签和新观察，最后一张是当前帧。"
 "将不穿插移动或明显视角调整的连续物体操作概括为一个交互段，只用一次interact；导航步骤保留方向，合法方向组合写成一个标签字符串。"
 "只预测当前之后的下一步骤或连续交互段，不输出后续路线。不能看到本轮参考答案、段内操作明细或段结束图片。"
 "必须只输出含action_semantics和action_labels的JSON，action_labels恰好一个字符串项，从31个合法写法中选择；具体交互语义不计分。只使用给定信息，不调用工具。")

def template():
    return files("egospatial").joinpath("resources/prompt.txt").read_text(encoding="utf-8")

def compile_request(ds, e, i):
    s = e["steps"][i]
    memories = e["spatial_memory"]
    frames = [m["frame"]["source_frame"] for m in memories]+[e["initial_frame"]]+[
        h["after_frame"] for h in e["steps"][:i]]
    if frames[-1] != s["before_frame"] or any(n >= e["initial_frame"] for n in frames[:len(memories)]):
        raise ValueError("Non-causal memory/history")
    if max(frames) != s["before_frame"] or s["after_frame"] in frames:
        raise ValueError("Future image leak")
    content = [{"type":"text","text":"任务："+e["goal"]},
               {"type":"text","text":"固定允许标签："+", ".join(LABELS)},
               {"type":"text","text":"以下为空间记忆参考帧，全部来自任务开始前，用于恢复空间布局；物体当前状态以当前帧为准。"}]
    count = 0
    def image(n):
        nonlocal count
        count += 1
        return {"type":"image","image":f"image_{count:03d}.jpg",
                "frame_id":frame(ds.data["video_id"],n)["id"]}
    for m in memories:
        n = m["frame"]["source_frame"]
        content += [{"type":"text","text":"空间记忆 "+m["id"]+"｜源帧"+str(n)+"｜"+m["description"]},image(n)]
    content += [{"type":"text","text":"空间记忆结束。下面是任务初始anchor与已执行的合并步骤历史。"},
                {"type":"text","text":"任务初始anchor｜源帧"+str(e["initial_frame"])+
                 ("；本轮anchor就是当前帧，只输入这一次。" if i == 0 else "。")},
                image(e["initial_frame"])]
    for j,h in enumerate(e["steps"][:i]):
        text = ("上一观察后已经执行的动作标签："+json.dumps(h["action_labels"],ensure_ascii=False)
                if h["action_labels"] else "该历史区间的标签待复核，只提供其结束观察")
        content += [{"type":"text","text":text},{"type":"text","text":
                    ("当前帧" if j == i-1 else "历史观察")+"｜源帧"+str(h["after_frame"])},
                    image(h["after_frame"])]
    content += [{"type":"text","text":template()}]
    messages = [{"role":"system","content":SYSTEM},{"role":"user","content":content}]
    prompt = ("这是空间记忆辅助的下一动作预测。附件按下文编号排列。仅根据记忆图、已发生动作和当前图回答。"
              "不要调用工具，不访问文件、网络或其他信息，不输出分析过程。\n\nSYSTEM："+SYSTEM+"\n\n")
    # A numbered text transcript exactly identifies every CLI attachment.
    for part in content:
        prompt += (part["text"] if part["type"] == "text" else
                   "[附件 "+part["image"]+"；"+part["frame_id"]+"]") + "\n"
    req = {"sample_id":e["episode_id"]+f"_s{i:04d}",
           "messages":messages,"prompt":prompt,"image_source_frames":frames,
           "image_sha256":[sha(ds.image(n)) for n in frames],
           "output_schema":schema(),"input_mode":'spatial_memory_anchor_executed_compound_label_prefix_current',
           "protocol":"spatial_memory_gt_prefix_v1"}
    req["input_sha256"] = digest({k:req[k] for k in
                                ("messages","image_sha256","input_mode")})
    return req
