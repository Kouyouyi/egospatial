"""One entry point for extraction, model replay, export and integrity verification."""
import argparse
import json
from pathlib import Path
from .io import read

def main():
    p = argparse.ArgumentParser(prog="egospatial")
    sub = p.add_subparsers(dest="command",required=True)
    x = sub.add_parser("package"); x.add_argument("directory"); x.add_argument("--output",required=True)
    x = sub.add_parser("stats"); x.add_argument("dataset")
    x = sub.add_parser("verify"); x.add_argument("directory")
    x = sub.add_parser("extract")
    for key in ("egoplan","epic","proposals","recipe","output"):
        x.add_argument("--"+key,required=True)
    x.add_argument("--egoplan-results",help="Optional sample_id join; never used as navigation labels")
    x = sub.add_parser("motion"); x.add_argument("--video",required=True);x.add_argument("--output",required=True)
    x = sub.add_parser("media")
    x.add_argument("--dataset",required=True);x.add_argument("--video",required=True)
    x.add_argument("--no-clips",action="store_true")
    x = sub.add_parser("download-metadata")
    x.add_argument("--kind",choices=["egoplan","epic"],required=True)
    x.add_argument("--video",default="P30_111");x.add_argument("--output",required=True)
    x = sub.add_parser("evaluate")
    for key in ("dataset","output","model"):
        x.add_argument("--"+key,required=True)
    x.add_argument("--backend",choices=["responses","codex"],default="responses")
    x.add_argument("--workers",type=int,default=1);x.add_argument("--retries",type=int,default=2)
    x.add_argument("--question");x.add_argument("--limit",type=int)
    x.add_argument("--reasoning",default="high");x.add_argument("--timeout",type=int,default=600)
    x.add_argument("--codex",default="codex")
    x = sub.add_parser("import-results")
    for key in ("dataset","review","output"):
        x.add_argument("--"+key,required=True)
    x = sub.add_parser("export")
    for key in ("dataset","run","output"):
        x.add_argument("--"+key,required=True)
    x.add_argument("--clips")
    x = sub.add_parser("pipeline");x.add_argument("config")
    a = p.parse_args()
    if a.command == "package":
        from .package import package
        result = package(a.directory,a.output)
    elif a.command == "stats":
        from .dataset import Dataset
        result = Dataset(a.dataset).stats()
    elif a.command == "verify":
        from .io import verify
        result = verify(a.directory)
    elif a.command == "extract":
        from .extraction import extract
        from .sources import select_results
        rows = read(a.egoplan)
        ids = {str(r["sample_id"]) for r in read(a.egoplan_results)} if a.egoplan_results else None
        result = extract(rows,read(a.epic),read(a.proposals),read(a.recipe),a.output,ids)
    elif a.command == "motion":
        from .motion import propose
        result = propose(a.video,a.output)
    elif a.command == "media":
        from .media import extract_media
        result = extract_media(a.dataset,a.video,not a.no_clips)
    elif a.command == "download-metadata":
        from .sources import epic_actions,egoplan_metadata
        result = (epic_actions(a.video,a.output) if a.kind == "epic"
                  else egoplan_metadata(a.output))
    elif a.command == "evaluate":
        from .evaluation import evaluate
        args = vars(a).copy();args.pop("command")
        result = evaluate(**args)
    elif a.command == "import-results":
        from .evaluation import import_review
        result = import_review(a.dataset,a.review,a.output)
    elif a.command == "export":
        from .export import export
        result = export(a.dataset,a.run,a.output,a.clips)
    elif a.command == "pipeline":
        result = pipeline(a.config)
    print(json.dumps(result,ensure_ascii=False,indent=2))

def pipeline(path):
    """All relative paths are relative to the config file, not the caller's cwd."""
    from .extraction import extract
    from .media import extract_media
    from .evaluation import evaluate
    from .export import export
    cfg = read(path);base = Path(path).resolve().parent
    def loc(key):
        return str((base/cfg[key]).resolve())
    dataset = loc("dataset")
    if cfg.get("extract",False):
        extract(read(loc("egoplan")),read(loc("epic")),read(loc("proposals")),
                read(loc("recipe")),dataset)
    if cfg.get("prepare_media",False):
        extract_media(dataset,loc("video"))
    result = evaluate(dataset,loc("run"),model=cfg["model"],backend=cfg.get("backend","responses"),
                      workers=cfg.get("workers",1),reasoning=cfg.get("reasoning","high"),
                      retries=cfg.get("retries",2),question=cfg.get("question"),
                      limit=cfg.get("limit"),codex=cfg.get("codex","codex"))
    export(dataset,loc("run"),loc("review"),loc("clips") if cfg.get("clips") else None)
    return result

if __name__ == "__main__":
    main()
