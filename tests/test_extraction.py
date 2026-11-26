from egospatial.extraction import extract
from egospatial.dataset import Dataset

def test_boundaries_merge_corrections_and_incomplete_tail(tmp_path):
    rows=[{"sample_id":1,"video_id":"S","current_observation_frame":5,"task_goal":"goal1","answer":"one"},
          {"sample_id":2,"video_id":"S","current_observation_frame":15,"task_goal":"goal2","answer":"two"}]
    events=[{"stop_frame":str(end-2),"start_frame":str(end-3),"narration":"operation"+str(end),
             "narration_id":str(end),"verb":"open"} for end in [7,9,14,20]]
    proposals={"proposals":[{"start":9,"end":12,"labels":["left"]}]}
    recipe={"video_id":"S","fps":50,"frame_count":20,
            "memory_slots":[{"id":"M","choices":[1],"description":"synthetic"}],
            "corrections":[{"question_id":1,"before_frame":9,"after_frame":12,
                            "components":["right","forward"],"semantics":"corrected"}]}
    output=tmp_path/"dataset.json"
    stats=extract(rows,events,proposals,recipe,output)
    ds=Dataset(output)
    first=ds.episodes[0]["steps"]
    assert [(s["before_frame"],s["after_frame"]) for s in first]==[(5,9),(9,12),(12,14),(14,15)]
    assert first[0]["component_count"]==2
    assert first[1]["action_labels"]==["right+forward"]
    assert first[1]["quality"]=="user_corrected_reference"
    assert first[-1]["completed"] is False
    assert stats["evaluable"]==4

    subset=tmp_path/"selected.json"
    extract(rows,events,proposals,recipe,subset,{"1"})
    selected=Dataset(subset)
    assert len(selected.episodes)==1
    assert selected.episodes[0]["final_frame"]==15
    assert selected.episodes[0]["next_question_id"]==2
