#!/usr/bin/env python3
"""Own API and worker children; terminate only those children on shutdown."""
import os, sys, subprocess, signal, time, argparse, socket
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=8765)
a = p.parse_args()
r = Path(__file__).resolve().parents[1]
e = Path(os.environ.get("EPISODE_STORAGE", "/Volumes/External Storage/Episode"))
if not (e / ".episode-storage").is_file():
    raise SystemExit("Configured Episode storage is unavailable")
with socket.socket() as check:
    check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    for attempt in range(20):
        try:
            check.bind(("127.0.0.1", a.port))
            break
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.25)
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
try:
    for args in [["worker"], ["serve", "--port", str(a.port)]]:
        children.append(subprocess.Popen([str(r / "scripts/episode"), *args], cwd=r))
    print(f"Episode: http://127.0.0.1:{a.port}", flush=True)
    while all(c.poll() is None for c in children):
        time.sleep(0.25)
finally:
    stop()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
