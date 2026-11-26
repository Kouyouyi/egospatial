"""Frame indices are one-based source indices; clips include both endpoints."""
from pathlib import Path
import json
import subprocess
from .dataset import Dataset
from .io import write

def extract_media(dataset, video, clips=True):
    ds = Dataset(dataset)
    wanted = sorted({n for e in ds.episodes for n in [
        e["initial_frame"],e["final_frame"],
        *[m["frame"]["source_frame"] for m in e["spatial_memory"]],
        *[s["before_frame"] for s in e["steps"]],*[s["after_frame"] for s in e["steps"]]]})
    missing = [n for n in wanted if not ds.image(n).exists()]
    if missing:
        from PIL import Image
        # Decode the source sequentially: seeking by timestamp can shift frame indices.
        width,height = 640,360
        command = ["ffmpeg","-v","error","-i",str(video),"-vf",f"scale={width}:{height}",
                   "-pix_fmt","rgb24","-vsync","0","-f","rawvideo","pipe:1"]
        proc = subprocess.Popen(command,stdout=subprocess.PIPE)
        try:
            targets, index = set(missing), 0
            while targets:
                raw = proc.stdout.read(width*height*3)
                index += 1
                if len(raw) != width*height*3:
                    raise RuntimeError("Video ended before required source frame")
                if index in targets:
                    path = ds.image(index)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    Image.frombytes("RGB",(width,height),raw).save(path,quality=95)
                    targets.remove(index)
        finally:
            proc.stdout.close()
            proc.terminate()
            proc.wait()
    if clips:
        for e in ds.episodes:
            path = ds.root/e["clip"]
            if not path.exists():
                path.parent.mkdir(parents=True,exist_ok=True)
                subprocess.run(["ffmpeg","-v","error","-ss",str((e["initial_frame"]-1)/ds.data["fps"]),
                    "-i",str(video),"-frames:v",str(e["final_frame"]-e["initial_frame"]+1),
                    "-vf","scale=640:360","-an","-c:v","libx264","-crf","25","-preset","veryfast",
                    "-threads","2","-movflags","+faststart",str(path)],check=True)
            info = json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
                    "-show_entries","stream=nb_frames,avg_frame_rate","-of","json",str(path)]))
            stream = info["streams"][0]
            if int(stream["nb_frames"]) != e["final_frame"]-e["initial_frame"]+1:
                raise ValueError("Clip frame count mismatch")
            numerator,denominator = map(int,stream["avg_frame_rate"].split("/"))
            if numerator/denominator != ds.data["fps"]:
                raise ValueError("Clip FPS mismatch")
    return {"source_frames":len(wanted),"new_frames":len(missing),"clips":len(ds.episodes) if clips else 0}
