"""The reference dataset is private to the compiler/scorer, never a model payload."""
from pathlib import Path
from .io import read, resolve
from .labels import normalize

def eligible(step):
    return bool(step.get("score_eligible") and step.get("completed")
                and step.get("taxonomy_status") != "requires_reannotation")

def frame(video, n):
    return {"id":f"{video}_f{n}", "video_id":video, "source_frame":int(n),
            "path":f"frames/frame_{int(n):010d}.jpg"}

class Dataset:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.root = self.path.parent
        self.data = read(self.path)
        self.episodes = self.data["episodes"]
        self.by_id = {e["episode_id"]:e for e in self.episodes}
        if len(self.by_id) != len(self.episodes):
            raise ValueError("Duplicate episode IDs")
        for e in self.episodes:
            previous = e["initial_frame"]
            if not e["spatial_memory"] or any(m["frame"]["source_frame"] >= previous
                                           for m in e["spatial_memory"]):
                raise ValueError("Spatial memory must precede task anchor")
            for s in e["steps"]:
                if s["before_frame"] != previous or s["after_frame"] <= previous:
                    raise ValueError("Non-contiguous action boundaries")
                previous = s["after_frame"]
                if eligible(s):
                    normalize(s["action_labels"])
            if previous != e["final_frame"]:
                raise ValueError("Episode endpoint mismatch")

    def cases(self, question=None):
        for e in self.episodes:
            if question is not None and str(e["question_id"]) != str(question):
                continue
            for i,s in enumerate(e["steps"]):
                if eligible(s):
                    yield e,i,s

    def image(self, n):
        return resolve(self.root, frame(self.data["video_id"],n)["path"])

    def stats(self):
        cases = list(self.cases())
        return {"dataset_version":self.data["dataset_version"],
                "task_intervals":len(self.episodes),
                "evaluable_task_intervals":len({e["episode_id"] for e,_,_ in cases}),
                "nodes":sum(len(e["steps"]) for e in self.episodes),
                "evaluable":len(cases),
                "navigation":sum(s["action_labels"] != ["interact"] for _,_,s in cases),
                "interact":sum(s["action_labels"] == ["interact"] for _,_,s in cases)}
