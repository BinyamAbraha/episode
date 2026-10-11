"""Bounded original-media inspection and traceable preview derivation."""

import subprocess, json, io, re, threading
from bisect import bisect_left

DECODE_LIMIT = threading.BoundedSemaphore(2)
from PIL import Image
from .storage import root, digest


def command(args, timeout=90):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-2000:])
    return result.stdout


def probe(path):
    return json.loads(
        command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,r_frame_rate,duration,nb_frames:format=duration",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def preview(path):
    sha = digest(path)
    out = root() / "derived" / (sha + ".webm")
    if not out.exists():
        staging = out.with_suffix(".partial.webm")
        args = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-threads",
            "2",
            "-i",
            str(path),
            "-an",
            "-c:v",
            "libvpx-vp9",
            "-threads",
            "2",
            "-deadline",
            "realtime",
            "-cpu-used",
            "6",
            "-crf",
            "34",
            "-b:v",
            "0",
            "-pix_fmt",
            "yuv420p",
            str(staging),
        ]
        command(args, timeout=240)
        staging.replace(out)
        out.with_suffix(".json").write_text(
            json.dumps(
                {
                    "source_sha256": sha,
                    "settings": args[args.index("-an") : -1],
                    "ffmpeg": command(["ffmpeg", "-version"]).decode().splitlines()[0],
                    "timing": "PTS retained, no frame rate conversion",
                    "sha256": digest(out),
                },
                indent=2,
            )
        )
    return out


def frame_times(path):
    out = root() / "derived" / (digest(path) + ".pts.json")
    if not out.exists():
        value = json.loads(
            command(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_frames",
                    "-show_entries",
                    "frame=best_effort_timestamp_time",
                    "-of",
                    "json",
                    str(path),
                ],
                timeout=120,
            )
        )
        times = [float(f["best_effort_timestamp_time"]) for f in value["frames"]]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Video PTS must be strictly increasing")
        out.write_text(json.dumps(times))
    return json.loads(out.read_text())


def decode_details(path, time):
    times = frame_times(path)
    i = bisect_left(times, time)
    candidates = [j for j in [i - 1, i] if 0 <= j < len(times)]
    index = min(candidates, key=lambda j: abs(times[j] - time))
    selected = times[index]
    if abs(selected - time) > 1 / 60 + 0.001:
        raise ValueError("No source frame within timing tolerance")
    with DECODE_LIMIT:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "info",
                "-threads",
                "1",
                "-copyts",
                "-ss",
                f"{max(0,selected-0.0001):.9f}",
                "-i",
                str(path),
                "-vf",
                "showinfo",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-threads",
                "1",
                "pipe:1",
            ],
            capture_output=True,
            timeout=30,
        )
    pts = re.findall(r"pts_time:([0-9.]+)", result.stderr.decode(errors="replace"))
    if result.returncode or not result.stdout or not pts:
        raise RuntimeError("Original frame decoding failed")
    actual = float(pts[0])
    if abs(actual - selected) > 0.001:
        raise ValueError(f"Decoded PTS {actual} differs from selected PTS {selected}")
    image = Image.open(io.BytesIO(result.stdout)).convert("RGB")
    image.load()
    return (
        image,
        result.stdout,
        {
            "requested_pts": time,
            "selected_pts": selected,
            "decoded_pts": actual,
            "frame_index": index,
            "error_seconds": abs(actual - time),
        },
    )


def decode(path, time):
    image, raw, _ = decode_details(path, time)
    return image, raw


def validate_stream(path, expected_shape):
    """Decode every original frame once and retain explicit validation evidence."""
    sha = digest(path)
    record = root() / "derived" / (sha + ".scan.json")
    if record.exists():
        return json.loads(record.read_text())
    metadata = probe(path)
    stream = metadata["streams"][0]
    if [stream["height"], stream["width"], 3] != expected_shape:
        raise ValueError("Video dimensions differ from declared feature")
    command(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-err_detect",
            "explode",
            "-threads",
            "2",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
        ],
        timeout=180,
    )
    times = frame_times(path)
    result = {
        "source_sha256": sha,
        "frames": len(times),
        "first_pts": times[0],
        "last_pts": times[-1],
        "codec": stream["codec_name"],
        "decode": "all frames; ffmpeg -xerror -err_detect explode",
        "tool": command(["ffmpeg", "-version"]).decode().splitlines()[0],
    }
    record.write_text(json.dumps(result, indent=2))
    return result


def existing_preview(path):
    out = root() / "derived" / (digest(path) + ".webm")
    if not out.is_file():
        raise RuntimeError(
            "Preview unavailable. Queue an import to restore its derived media."
        )
    return out
