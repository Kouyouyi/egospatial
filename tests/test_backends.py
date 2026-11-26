import base64
from egospatial.protocol import compile_request
from egospatial.backends import responses_payload

def test_responses_uses_only_ordered_public_images(dataset):
    req=compile_request(dataset,dataset.episodes[0],1)
    images=[dataset.image(n) for n in req["image_source_frames"]]
    body=responses_payload(req,images,"fake")
    assert "tools" not in body and body["store"] is False
    assert body["text"]["format"]["schema"]==req["output_schema"]
    actual=[p["image_url"] for p in body["input"][0]["content"] if p["type"]=="input_image"]
    assert len(actual)==3
    for url,path in zip(actual,images):
        assert base64.b64decode(url.split(",",1)[1])==path.read_bytes()
    assert all(str(path) not in str(body) for path in images)

def test_codex_cli_rejects_tool_events(dataset,monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from egospatial.backends import Codex
    import json
    import pytest
    req=compile_request(dataset,dataset.episodes[0],0)
    images=[dataset.image(n) for n in req["image_source_frames"]]
    def process(args,**kwargs):
        assert "--ignore-user-config" in args and "--ephemeral" in args
        assert kwargs["input"]==req["prompt"]
        Path(args[args.index("--output-last-message")+1]).write_text('{"action_semantics":"x","action_labels":["up"]}')
        return SimpleNamespace(returncode=0,stdout=json.dumps(
            {"type":"item.completed","item":{"type":"command_execution"}}),stderr="")
    monkeypatch.setattr("egospatial.backends.subprocess.run",process)
    with pytest.raises(RuntimeError,match="extra tool"):
        Codex("fake")(req,images)
