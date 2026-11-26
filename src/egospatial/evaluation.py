"""Resumable, immutable-input GT replay; retries transport failures, never wrong answers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import contextlib
import fcntl
import time
import uuid
from . import backends
from .dataset import Dataset
from .io import read, write, digest
from .labels import score, schema
from .protocol import compile_request, template, SYSTEM

def evaluate(dataset, output, model, backend="responses", workers=1, retries=2,
             question=None, limit=None, reasoning="high", timeout=600,
             codex="codex", adapter=None):
    ds, root = Dataset(dataset), Path(output)
    root.mkdir(parents=True,exist_ok=True)
    # Lock the whole batch, preventing two processes from overwriting the same cases.
    with (root/".batch.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        config = {"dataset_version":ds.data["dataset_version"],"dataset_sha256":digest(ds.data),
                  "model":model,"backend":backend,"reasoning":reasoning,
                  "protocol":"spatial_memory_gt_prefix_v1",
                  "prompt_sha256":digest([SYSTEM,template(),schema()])}
        if (root/"config.json").exists() and read(root/"config.json") != config:
            raise ValueError("Run config changed; choose another output directory")
        write(root/"config.json",config)
        cases = list(ds.cases(question))
        if limit is not None:
            cases = cases[:limit]
        call = adapter or {"responses":backends.Responses,"codex":backends.Codex}[backend](
            model=model,reasoning=reasoning,timeout=timeout,codex=codex)
        def run(case):
            e,i,reference = case
            req = compile_request(ds,e,i)
            cid = req["sample_id"]
            dest = root/"cases"/(cid+".json")
            if dest.exists():
                old = read(dest)
                if old["request"]["input_sha256"] != req["input_sha256"]:
                    raise ValueError("Input bytes changed: "+cid)
                if old["output"]["status"] == "completed":
                    return old
            images = [ds.image(n) for n in req["image_source_frames"]]
            started = time.monotonic()
            failure_types = []
            for attempt in range(retries+1):
                try:
                    result = call(req,images)
                    out = dict(result,status="completed",run_id=uuid.uuid4().hex,
                               reference_answer_sent=False,
                               duration_seconds=round(time.monotonic()-started,3),
                               finished_unix=time.time())
                    break
                except Exception as exc:
                    failure_types.append(type(exc).__name__)
                    if attempt < retries:
                        time.sleep(min(2**attempt,8))
                    else:
                        out = {"status":"failed","model":model,"run_id":uuid.uuid4().hex,
                               "error_types":failure_types,"reference_answer_sent":False}
            row = {"id":cid,"episode_id":e["episode_id"],"question_id":e["question_id"],
                   "step_index":i,"request":req,"output":out,
                   "score":score(out["answer"],reference["action_labels"])
                           if out["status"] == "completed" else None,
                   "reference":{"action_labels":reference["action_labels"],
                                "action_semantics":reference["action_semantics"],
                                "quality":reference["quality"]}}
            write(dest,row)
            return row
        with ThreadPoolExecutor(max_workers=max(1,workers)) as pool:
            for future in as_completed([pool.submit(run,c) for c in cases]):
                row = future.result()
                print(row["id"],row["output"]["status"],flush=True)
        rows = [read(root/"cases"/(e["episode_id"]+f"_s{i:04d}.json")) for e,i,_ in cases]
        summary = metrics(rows)
        write(root/"summary.json",summary)
        return summary

def metrics(rows):
    def group(selected):
        done = [x for x in selected if x["output"]["status"] == "completed"]
        correct = sum(x["score"]["correct"] for x in done)
        return {"expected":len(selected),"completed":len(done),"correct":correct,
                "accuracy":correct/len(done) if done else None,
                "failed":len(selected)-len(done),
                "label_valid":sum(x["score"]["label_valid"] for x in done),
                "format_valid":sum(x["score"]["format_valid"] for x in done)}
    return {"all":group(rows),
            "navigation":group([x for x in rows if x["reference"]["action_labels"] != ["interact"]]),
            "interact":group([x for x in rows if x["reference"]["action_labels"] == ["interact"]])}

def import_review(dataset, review, output):
    """Import existing actual requests/outputs without changing or rerunning the model."""
    ds, source, root = Dataset(dataset), Path(review), Path(output)
    index = read(source/"index.json")
    if index["dataset_version"] != ds.data["dataset_version"]:
        raise ValueError("Dataset/review version mismatch")
    expected = {e["episode_id"]+f"_s{i:04d}":(e,i,s) for e,i,s in ds.cases()}
    if set(expected) != {x["id"] for x in index["samples"]}:
        raise ValueError("Review does not cover the dataset exactly")
    rows = []
    for item in index["samples"]:
        s = read(source/item["detail_json"])
        e,i,reference = expected[s["id"]]
        req = s["request"]
        now = compile_request(ds,e,i)
        # Historical CLI wrapper text differs; logical messages and attachment bytes are exact.
        for key in ("messages","image_sha256","image_source_frames","output_schema","input_mode"):
            if req[key] != now[key]:
                raise ValueError("Historical input mismatch: "+s["id"]+" / "+key)
        out = read(source/s["output_file"])
        if out["status"] != "completed" or out.get("reference_answer_sent") is not False:
            raise ValueError("Invalid historical output")
        sc = score(out["answer"],reference["action_labels"])
        if sc["correct"] != s["score"]["correct"]:
            raise ValueError("Historical score mismatch")
        row = {"id":s["id"],"episode_id":e["episode_id"],"question_id":e["question_id"],
               "step_index":i,"request":req,"output":out,"score":sc,"reference":s["reference"]}
        write(root/"cases"/(s["id"]+".json"),row)
        rows.append(row)
    write(root/"config.json",{"dataset_version":ds.data["dataset_version"],
          "model":index["model"],"backend":"historical_codex_import",
          "protocol":"spatial_memory_gt_prefix_v1","source":"actual completed requests and outputs"})
    result = metrics(rows)
    write(root/"summary.json",result)
    return result
