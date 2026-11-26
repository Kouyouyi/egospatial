"""Obtain metadata only; raw EPIC videos follow the upstream access/download process."""
from pathlib import Path
import csv
import io
import json
import requests
from .io import write

EPIC_REV = "ea8b40457a400c3fffa1c7f406ef3dc169cc2522"
EGOPLAN_REV = "515f017faf0cdf42a25654a1bcd879c12277eff1"

def epic_actions(video, output):
    rows = []
    for split in ("train","validation"):
        url = f"https://raw.githubusercontent.com/epic-kitchens/epic-kitchens-100-annotations/{EPIC_REV}/EPIC_100_{split}.csv"
        response = requests.get(url,timeout=120)
        response.raise_for_status()
        rows.extend(r for r in csv.DictReader(io.StringIO(response.text)) if r["video_id"] == video)
    if not rows:
        raise ValueError("Video not found in EPIC train/validation annotations")
    write(output,rows)
    return {"video_id":video,"actions":len(rows),"revision":EPIC_REV}

def egoplan_metadata(output, revision=EGOPLAN_REV):
    from huggingface_hub import HfApi,hf_hub_download
    import pyarrow.parquet as pq
    api = HfApi()
    names = api.list_repo_files("lmms-lab/EgoPlan",repo_type="dataset",revision=revision)
    names = [n for n in names if n.endswith(".parquet")]
    if not names:
        raise ValueError("No annotation parquet found in pinned EgoPlan release")
    rows = []
    for name in names:
        path = hf_hub_download("lmms-lab/EgoPlan",name,repo_type="dataset",revision=revision)
        for row in pq.read_table(path).to_pylist():
            # Preserve raw rows when their schema is already the released EgoPlan JSON schema.
            if "sample_id" in row and "current_observation_frame" in row:
                rows.append(row)
            elif "question" in row and "answer" in row and "task_progress_metadata" in row:
                rows.append(row)
            else:
                raise ValueError("Unexpected upstream parquet schema; use original EgoPlan_validation.json")
    write(output,rows)
    return {"rows":len(rows),"revision":revision,"files":names}

def convert_parquet(source, output):
    import pyarrow.parquet as pq
    rows = pq.read_table(source).to_pylist()
    write(output,rows)
    return {"rows":len(rows)}

def select_results(rows, results):
    """Optional join of official evaluation outputs, never movement-label generation."""
    if results is None:
        return rows
    ids = {str(r["sample_id"]) for r in results}
    return [r for r in rows if str(r["sample_id"]) in ids]
