"""EgoPlan question boundaries + EPIC interactions + motion proposals -> latest format."""
import copy
from .dataset import frame, Dataset
from .labels import NAV, encode
from .io import read, write, digest

def extract(egoplan, epic, proposals, recipe, output, selected_ids=None):
    rows = sorted([r for r in egoplan if r["video_id"] == recipe["video_id"]],
                  key=lambda r:r["current_observation_frame"])
    if not rows:
        raise ValueError("No matching EgoPlan questions")
    video = recipe["video_id"]
    episodes = []
    for k,r in enumerate(rows):
        start = int(r["current_observation_frame"])
        end = int(rows[k+1]["current_observation_frame"]) if k+1<len(rows) else recipe["frame_count"]
        memory = []
        for slot in recipe["memory_slots"]:
            choices = [n for n in slot["choices"] if n < start]
            if choices:
                memory.append({"id":slot["id"],"description":slot["description"],
                               "frame":frame(video,max(choices))})
        points, truncated = [], []
        for event in epic:
            after = int(event["stop_frame"])+2
            if start < after <= end:
                points.append({"end":after,"semantics":event["narration"],
                               "labels":["interact"],"quality":"official_interaction_boundary",
                               "source":event["narration_id"]})
            elif int(event["start_frame"])+1 <= end < after and after > start:
                truncated.append(event["narration_id"])
        for m in proposals["proposals"]:
            if start < m["end"] <= end and m["start"] >= start:
                points.append({"end":m["end"],"semantics":"相机运动候选："+",".join(m["labels"]),
                               "labels":m["labels"],"quality":"automatic_navigation_unreviewed",
                               "source":"robust_background_affine_flow_5Hz"})
        steps, previous = [], start
        for point in sorted(points,key=lambda p:p["end"]):
            if steps and point["end"] == steps[-1]["after_frame"]:
                steps[-1]["action_semantics"] += "；"+point["semantics"]
                steps[-1]["action_labels"] = sorted(set(steps[-1]["action_labels"]+point["labels"]))
                steps[-1]["quality"] = "mixed_or_simultaneous_draft"
                continue
            steps.append({"step_id":f"q{r['sample_id']}_s{len(steps):04d}",
                          "before_frame":previous,"after_frame":point["end"],
                          "action_semantics":point["semantics"],"action_labels":sorted(set(point["labels"])),
                          "quality":point["quality"],"source":point["source"],
                          "score_eligible":True,"completed":True})
            previous = point["end"]
        if previous < end:
            steps.append({"step_id":f"q{r['sample_id']}_tail","before_frame":previous,"after_frame":end,
                          "action_semantics":"片段末尾观察；未给未完成动作伪造结束标签",
                          "action_labels":[],"quality":"truncated_or_unannotated_tail",
                          "score_eligible":False,"completed":False,"source":"interval_tail"})
        goal = "当前任务："+r["task_goal"]+"。"+(
            "随后推进到："+rows[k+1]["task_goal"]+"，准备执行："+rows[k+1]["answer"]+"。"
            if k+1<len(rows) else "继续到视频片段结束。")
        override = recipe.get("episode_overrides",{}).get(str(r["sample_id"]))
        if override:
            steps = copy.deepcopy(override["steps"])
            goal = override["goal"]
        # Merge only contiguous, pure interactions, never a movement/mixed/tail boundary.
        groups = []
        for s in steps:
            if (groups and s["action_labels"] == ["interact"] and
                groups[-1][-1]["action_labels"] == ["interact"] and
                groups[-1][-1]["after_frame"] == s["before_frame"]):
                groups[-1].append(s)
            else:
                groups.append([s])
        merged = []
        for j,group in enumerate(groups):
            s = copy.deepcopy(group[0])
            s.update(step_id=f"q{r['sample_id']}_m{j:04d}",
                     before_frame=group[0]["before_frame"],after_frame=group[-1]["after_frame"],
                     source_steps=copy.deepcopy(group),source_step_ids=[x["step_id"] for x in group],
                     component_count=len(group),
                     completed=all(x["completed"] for x in group),
                     score_eligible=all(x["score_eligible"] and x["completed"] for x in group))
            if len(group)>1:
                texts = []
                for x in group:
                    t = x["action_semantics"].strip()
                    if not texts or texts[-1] != t:
                        texts.append(t)
                key = ",".join(s["source_step_ids"])
                s["action_semantics"] = recipe.get("interaction_summaries",{}).get(
                    key,"在当前操作区域连续完成："+"；".join(texts))
                s["quality"] = "merged_interaction_sequence_draft"
                s["source"] = " | ".join(str(x["source"]) for x in group)
            correction = next((c for c in recipe.get("corrections",[])
                               if c["question_id"] == r["sample_id"] and
                               c["before_frame"] == s["before_frame"] and
                               c["after_frame"] == s["after_frame"]),None)
            if correction:
                s["action_labels"] = correction["components"]
                s["action_semantics"] = correction["semantics"]
                s["quality"] = "user_corrected_reference"
                s["source"] = "explicit user correction: "+" + ".join(correction["components"])
                s["reference_correction"] = copy.deepcopy(correction)
                for source in s["source_steps"]:
                    source.update(action_labels=correction["components"],
                                  action_semantics=s["action_semantics"],
                                  quality=s["quality"],source=s["source"])
            s["label_components"] = list(s["action_labels"])
            try:
                s["action_labels"] = encode(s["action_labels"])
            except ValueError:
                s.update(action_labels=[],score_eligible=False,taxonomy_status="requires_reannotation",
                         exclusion_reason="legacy reference mixes interact with movement or has more than two directions")
            merged.append(s)
        episodes.append({"episode_id":f"{video}_q{r['sample_id']}_v1","question_id":r["sample_id"],
                         "next_question_id":rows[k+1]["sample_id"] if k+1<len(rows) else None,
                         "original_question":r,"goal":goal,"initial_frame":start,"final_frame":end,
                         "clip":f"clips/q{r['sample_id']}.mp4","spatial_memory":memory,
                         "steps":merged,"truncated_source_events":truncated,
                         "quality":"draft_dataset_not_final_human_verified_GT"})
    if selected_ids is not None:
        episodes = [e for e in episodes if str(e["question_id"]) in selected_ids]
        if not episodes:
            raise ValueError("No matching result sample IDs")
    d = {"schema_version":"egospatial_dataset_v1","video_id":video,"fps":recipe["fps"],
         "frame_count":recipe["frame_count"],"episodes":episodes,
         "provenance":{"egoplan_question_boundaries":True,"navigation":"2D optical-flow draft; not pose GT",
                       "recipe_sha256":digest(recipe),"proposal_sha256":digest(proposals)},
         "reference_status":"draft, with explicit user correction; requires further human review"}
    d["dataset_version"] = "egospatial_"+digest(d)[:12]
    write(output,d)
    return Dataset(output).stats()
