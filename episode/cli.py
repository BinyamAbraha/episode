import argparse, json, shutil, subprocess
from .storage import *
from .service import enqueue, create_version, verify_version, version


def main():
    p = argparse.ArgumentParser(prog="episode")
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("doctor")
    s.add_parser("validate")
    c = s.add_parser("cleanup")
    c.add_argument("--apply", action="store_true")
    i = s.add_parser("import")
    i.add_argument("--limit", type=int, default=50)
    w = s.add_parser("worker")
    w.add_argument("--once", action="store_true")
    a = s.add_parser("serve")
    a.add_argument("--port", type=int, default=8765)
    v = s.add_parser("version")
    v.add_argument("name")
    v.add_argument("--accepted-only", action="store_true")
    q = s.add_parser("verify")
    q.add_argument("version")
    x = s.add_parser("export")
    x.add_argument("version")
    x.add_argument("destination")
    c = s.add_parser("catalog")
    c.add_argument("--review", default="")
    c.add_argument("--search", default="")
    d = s.add_parser("inspect")
    d.add_argument("episode", type=int)
    rv = s.add_parser("review")
    rv.add_argument("episode", type=int)
    rv.add_argument("status", choices=["accepted", "excluded", "unreviewed"])
    rv.add_argument("--reason", required=True)
    rv.add_argument(
        "--outcome", default="unknown", choices=["unknown", "success", "failure"]
    )
    an = s.add_parser("annotate")
    an.add_argument("episode", type=int)
    an.add_argument("start", type=float)
    an.add_argument("end", type=float)
    an.add_argument("label")
    an.add_argument("--note", default="")
    sel = s.add_parser("selection")
    sel.add_argument("name")
    sel.add_argument("--review", default="")
    cp = s.add_parser("compare")
    cp.add_argument("left")
    cp.add_argument("right")
    args = p.parse_args()
    from . import service

    if args.command == "catalog":
        print(
            json.dumps(
                service.catalog({"review": args.review, "search": args.search}),
                indent=2,
            )
        )
        return
    if args.command == "inspect":
        result = service.episode(args.episode)
        result["sample_count"] = len(result.pop("samples"))
        print(json.dumps(result, indent=2))
        return
    if args.command == "review":
        service.review(args.episode, args.status, args.outcome, args.reason)
        print("Review appended")
        return
    if args.command == "annotate":
        service.annotate(args.episode, args.start, args.end, args.label, args.note)
        print("Annotation appended")
        return
    if args.command == "selection":
        criteria = {"review": args.review, "valid_only": True}
        with connect() as db:
            db.execute(
                "INSERT INTO selections(name,criteria,created) VALUES(?,?,?)",
                (args.name, canonical(criteria), now()),
            )
        chosen = [e for e in service.catalog(criteria) if e["review"] != "excluded"]
        print(
            json.dumps(
                {
                    "selected": len(chosen),
                    "excluded": len(service.catalog()) - len(chosen),
                }
            )
        )
        return
    if args.command == "compare":
        a = version(args.left)
        b = version(args.right)
        print(
            json.dumps(
                {
                    "added": sorted(set(b["episodes"]) - set(a["episodes"])),
                    "removed": sorted(set(a["episodes"]) - set(b["episodes"])),
                    "changed": [
                        k
                        for k in [
                            "criteria",
                            "split",
                            "rules",
                            "transforms",
                            "normalization",
                            "reviews",
                            "annotations",
                        ]
                        if a[k] != b[k]
                    ],
                },
                indent=2,
            )
        )
        return
    if args.command == "doctor":
        print(
            json.dumps(
                {
                    "storage": str(root()),
                    "free_bytes": shutil.disk_usage(root()).free,
                    "ffmpeg": shutil.which("ffmpeg"),
                    "ffprobe": shutil.which("ffprobe"),
                    "python": subprocess.check_output(
                        ["python3.11", "--version"], text=True
                    ).strip(),
                },
                indent=2,
            )
        )
    elif args.command == "cleanup":
        from .retention import cleanup_staging

        print(json.dumps(cleanup_staging(args.apply), indent=2))
    elif args.command == "validate":
        print(enqueue(args={"limit": 50}))
    elif args.command == "import":
        print(enqueue(args={"limit": args.limit}))
    elif args.command == "worker":
        from .worker import run

        run(args.once)
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("episode.api:app", host="127.0.0.1", port=args.port)
    elif args.command == "version":
        print(
            create_version(
                args.name,
                {"review": "accepted"} if args.accepted_only else {"valid_only": True},
            )
        )
    elif args.command == "verify":
        print(json.dumps(verify_version(args.version), indent=2))
    elif args.command == "export":
        with open(args.destination, "x") as f:
            f.write(canonical(version(args.version)) + "\n")


if __name__ == "__main__":
    main()
