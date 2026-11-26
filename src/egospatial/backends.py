"""Model adapters receive a public request and its images, never the reference node."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import requests

def responses_payload(request, images, model, reasoning="high"):
    content, iterator = [], iter(images)
    for part in request["messages"][1]["content"]:
        if part["type"] == "text":
            content.append({"type":"input_text","text":part["text"]})
        else:
            raw = base64.b64encode(Path(next(iterator)).read_bytes()).decode()
            content.append({"type":"input_image","image_url":"data:image/jpeg;base64,"+raw})
    body = {"model":model,"instructions":request["messages"][0]["content"],
            "input":[{"role":"user","content":content}], "store":False,
            "text":{"format":{"type":"json_schema","name":"next_action","strict":True,
                              "schema":request["output_schema"]}}}
    if reasoning:
        body["reasoning"] = {"effort":reasoning}
    return body

class Responses:
    def __init__(self, model, reasoning="high", timeout=600, **_):
        self.model, self.reasoning, self.timeout = model, reasoning, timeout

    def __call__(self, request, images):
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY for the responses backend")
        body = responses_payload(request,images,self.model,self.reasoning)
        response = requests.post("https://api.openai.com/v1/responses",
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
            json=body,timeout=self.timeout)
        if response.status_code >= 400:
            # Do not persist credential-bearing headers or arbitrary server error bodies.
            raise RuntimeError("Responses HTTP "+str(response.status_code))
        raw = response.json()
        if raw.get("status") != "completed":
            raise RuntimeError("Responses result is incomplete or refused")
        answer = "".join(p.get("text","") for item in raw.get("output",[])
                         if item.get("type") == "message"
                         for p in item.get("content",[]) if p.get("type") == "output_text")
        if not answer:
            raise RuntimeError("Responses returned no output text")
        return {"answer":answer,"usage":raw.get("usage"),"raw_response":raw,
                "model":raw.get("model",self.model),"provider":"openai_responses"}

class Codex:
    def __init__(self, model, reasoning="high", timeout=600, codex="codex", **_):
        self.model, self.reasoning, self.timeout, self.codex = model, reasoning, timeout, codex

    def __call__(self, request, images):
        with tempfile.TemporaryDirectory(prefix="egospatial_") as tmp:
            root = Path(tmp)
            args = [self.codex,"exec","--ignore-user-config","--ephemeral",
                    "--skip-git-repo-check","--sandbox","read-only","--cd",tmp,
                    "--model",self.model,"-c",'model_reasoning_effort='+json.dumps(self.reasoning),
                    "--json","--output-last-message",str(root/"answer.txt"),
                    "--output-schema",str(root/"schema.json")]
            (root/"schema.json").write_text(json.dumps(request["output_schema"]))
            for i,path in enumerate(images,1):
                dest = root/f"image_{i:03d}.jpg"
                shutil.copyfile(path,dest)
                args += ["--image",str(dest)]
            args += ["-"]
            proc = subprocess.run(args,input=request["prompt"],capture_output=True,
                                  text=True,timeout=self.timeout)
            if proc.returncode or not (root/"answer.txt").exists():
                raise RuntimeError("Codex CLI failed; check login, model access and CLI version")
            events = []
            for line in proc.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            if any(x.get("item",{}).get("type") in
                   {"command_execution","mcp_tool_call","web_search","file_change"}
                   for x in events):
                raise RuntimeError("Pure-vision run rejected: extra tool use")
            if any(x.get("type") in {"error","turn.failed"} for x in events):
                raise RuntimeError("Codex turn failed")
            answer = (root/"answer.txt").read_text().strip()
            if not answer:
                raise RuntimeError("Empty Codex answer")
            usage = next((x.get("usage") for x in reversed(events)
                          if x.get("type") == "turn.completed"),None)
            # Only model events are retained; stderr may include machine configuration.
            return {"answer":answer,"usage":usage,"raw_events":events,
                    "model":self.model,"provider":"codex_cli"}
