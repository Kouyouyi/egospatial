"""Offline latest-only review: actual model inputs are separate from scoring references."""
from importlib.resources import files
from pathlib import Path
import json
import shutil
import time
from .dataset import Dataset
from .io import read, write, sha, manifest
from .evaluation import metrics
from .labels import LABELS, schema

def js(obj):
    return json.dumps(obj,ensure_ascii=False,separators=(",",":")).replace("</","<\\/").replace("\u2028","\\u2028").replace("\u2029","\\u2029")

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists() or sha(src) != sha(dst):
        shutil.copyfile(src,dst)

def export(dataset, run, output, clips=None):
    ds, run, root = Dataset(dataset), Path(run), Path(output)
    # Do not silently keep stale samples from another export/version.
    if root.exists() and any(root.iterdir()):
        raise ValueError("Review output must be an empty directory")
    root.mkdir(parents=True,exist_ok=True)
    config = read(run/"config.json")
    if config["dataset_version"] != ds.data["dataset_version"]:
        raise ValueError("Run/dataset version mismatch")
    entries, records, episodes, rows = [], [], [], []
    clips = Path(clips) if clips else ds.root/"clips"
    for e in ds.episodes:
        indices = [(i,s) for _,i,s in ds.cases(e["question_id"])]
        episodes.append({"episode_id":e["episode_id"],"question_id":e["question_id"],
                         "goal":e["goal"],"count":len(indices),
                         "initial_frame":e["initial_frame"],"final_frame":e["final_frame"]})
        video_file = None
        if indices:
            source = next((p for p in [clips/f"q{e['question_id']}.mp4",
                                     clips/f"{e['question_id']}.mp4"] if p.exists()),None)
            if source:
                video_file = f"videos/{e['question_id']}.mp4"
                copy(source,root/video_file)
        for i,step in indices:
            cid = e["episode_id"]+f"_s{i:04d}"
            path = run/"cases"/(cid+".json")
            row = read(path) if path.exists() else None
            ready = bool(row and row["output"]["status"] == "completed")
            item = {"id":cid,"ordinal":len(entries)+1,"episode_id":e["episode_id"],
                    "question_id":e["question_id"],"step_index":i,"goal":e["goal"],
                    "current_frame":step["before_frame"],"after_frame":step["after_frame"],
                    "expected_labels":step["action_labels"],"reference_quality":step["quality"],
                    "reference_semantics":step["action_semantics"],
                    "kind":"interact" if step["action_labels"] == ["interact"] else "navigation",
                    "status":"completed" if ready else "pending",
                    "detail_js":f"samples/{cid}.js","detail_json":f"samples/{cid}.json"}
            if row:
                rows.append(row)
            if ready:
                req, out, score = row["request"], row["output"], row["score"]
                image_files = []
                for n,expected_sha in zip(req["image_source_frames"],req["image_sha256"]):
                    src = ds.image(n)
                    if sha(src) != expected_sha:
                        raise ValueError("Image changed since inference")
                    name = f"images/{expected_sha}.jpg"
                    copy(src,root/name)
                    image_files.append(name)
                out_id = out["run_id"]
                request_file, output_file = f"requests/{out_id}.json",f"outputs/{out_id}.json"
                write(root/request_file,req)
                write(root/output_file,out)
                after = f"frames/f{step['after_frame']}.jpg"
                copy(ds.image(step["after_frame"]),root/after)
                memory = [dict(id=m["id"],description=m["description"],
                               source_frame=m["frame"]["source_frame"],image_file=image_files[j])
                          for j,m in enumerate(e["spatial_memory"])]
                payload = {"id":cid,"ordinal":item["ordinal"],"run_id":out_id,
                           "dataset_version":ds.data["dataset_version"],"episode_id":e["episode_id"],
                           "question_id":e["question_id"],"step_index":i,"goal":e["goal"],
                           "current_frame":step["before_frame"],"after_frame":step["after_frame"],
                           "spatial_memory":memory,"image_files":image_files,
                           "request":req,"request_file":request_file,"output_file":output_file,
                           "output":{k:out.get(k) for k in ("run_id","status","model","answer",
                                     "duration_seconds","usage","finished_unix")},
                           "reference":{"action_labels":step["action_labels"],
                                        "action_semantics":step["action_semantics"],
                                        "quality":step["quality"],"component_steps":step.get("source_steps",[]),
                                        "after_image_file":after},
                           "score":score,
                           "video":{"file":video_file,"start_frame":e["initial_frame"],
                                    "end_frame":e["final_frame"],"fps":ds.data["fps"]},
                           "audit":{"past_memory_only":True,"no_current_answer_or_after_image_sent":True,
                                    "actual_attachment_hashes_verified":True}}
                write(root/item["detail_json"],payload)
                (root/item["detail_js"]).write_text("window.latestBenchCaseReady("+js(cid)+","+js(payload)+");\n")
                try:
                    semantics = json.loads(out["answer"]).get("action_semantics","")
                except ValueError:
                    semantics = ""
                item.update(run_id=out_id,predicted_labels=score["predicted_labels"],
                            correct=score["correct"],label_valid=score["label_valid"],
                            prediction_semantics=semantics)
                records.append(payload)
            entries.append(item)
    summary = metrics(rows)
    # Include pending cases in the expected denominator, but never count them as wrong.
    for name in summary:
        matching = [x for x in entries if name == "all" or x["kind"] == name]
        summary[name]["expected"] = len(matching)
        summary[name]["pending"] = len(matching)-summary[name]["completed"]-summary[name]["failed"]
    index = {"schema_version":"latest_gpt_bench_index_v1","dataset_version":ds.data["dataset_version"],
             "batch_id":run.name,"model":config["model"],"updated_unix":time.time(),
             "total":len(entries),"completed":len(records),"pending":len(entries)-len(records),
             "source_task_intervals":len(episodes),"evaluable_task_intervals":sum(e["count"]>0 for e in episodes),
             "summary":summary,"episodes":episodes,"samples":entries,"archive_ready":True,
             "reference_status":"draft labels; exact direction-set agreement, not task success",
             "input_protocol":"spatial_memory_gt_prefix_v1",
             "evaluation_policy":"complete eligible nodes only; fixed GT history; current answer withheld",
             "label_vocabulary":LABELS}
    write(root/"index.json",index)
    (root/"index.js").write_text("window.latestBenchIndexReady("+js(index)+");\n")
    html = files("egospatial").joinpath("resources/viewer.html").read_text(encoding="utf-8")
    (root/"review.html").write_text(html.replace("__INDEX__",js(index)),encoding="utf-8")
    with (root/"all-results.jsonl").open("w") as f:
        for row in records:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    write(root/"output-schema.json",schema())
    write(root/"taxonomy.json",{"labels":LABELS,"semantic_action_count":19})
    (root/"compound-memory-prompt-template.txt").write_text(
        files("egospatial").joinpath("resources/prompt.txt").read_text(encoding="utf-8"))
    write(root/"reference-corrections.json",ds.data.get("reference_corrections",[]))
    write(root/"taxonomy-review-needed.json",[
        {"episode_id":e["episode_id"],"step_index":i,**s}
        for e in ds.episodes for i,s in enumerate(e["steps"])
        if s.get("taxonomy_status") == "requires_reannotation"])
    write(root/"verification.json",{"dataset_version":ds.data["dataset_version"],"total_samples":len(entries),
                                   "completed":len(records),"summary":summary,
                                   "current_gt_or_future_image_sent":False})
    (root/"README.md").write_text("# egospatial review\n打开 review.html 查看当前版本的实际输入、模型输出、参考标签和任务视频。\n")
    write(root/"SHA256SUMS.json",manifest(root))
    return {"output":str(root),"total":len(entries),"completed":len(records),"summary":summary}
