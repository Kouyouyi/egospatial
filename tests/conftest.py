import pytest
from PIL import Image
from egospatial.io import write
from egospatial.dataset import Dataset, frame

@pytest.fixture
def dataset(tmp_path):
    def step(a,b,labels,eligible=True,complete=True):
        return {"before_frame":a,"after_frame":b,"action_labels":labels,
                "action_semantics":"SECRET_NEXT_REFERENCE","quality":"synthetic",
                "completed":complete,"score_eligible":eligible}
    data = {"dataset_version":"synthetic-v1","video_id":"SYNTH","fps":50,"frame_count":20,
            "episodes":[{"episode_id":"SYNTH_q1","question_id":1,"next_question_id":None,
             "goal":"Find the synthetic target","initial_frame":5,"final_frame":20,
             "spatial_memory":[{"id":"M01","description":"Synthetic room",
                                "frame":frame("SYNTH",1)}],
             "steps":[step(5,8,["interact"]),step(8,12,["right+forward"]),
                      step(12,15,[],False),step(15,18,["up"]),
                      step(18,20,[],False,False)],"clip":"clips/q1.mp4"}]}
    path = tmp_path/"benchmark/dataset.json"
    write(path,data)
    for n in [1,5,8,12,15,18,20]:
        p = path.parent/frame("SYNTH",n)["path"]
        p.parent.mkdir(parents=True,exist_ok=True)
        Image.new("RGB",(32,18),(n*10,0,0)).save(p)
    return Dataset(path)
