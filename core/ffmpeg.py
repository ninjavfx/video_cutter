import json
import os
import subprocess
import tempfile
import time
from typing import Callable, List, Optional

from core.segment import Segment


class FFmpegError(Exception):
    pass


def probe_video(filepath: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise FFmpegError(f"ffprobe failed: {e}") from e
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise FFmpegError("No video stream found")

    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0:
        duration = float(video_stream.get("duration", 0))

    return {
        "duration": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": _parse_fps(video_stream),
        "codec": video_stream.get("codec_name", ""),
    }


def _parse_fps(stream: dict) -> float:
    fps_str = stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        num, den = int(num), int(den)
        return num / den if den else 30.0
    return float(fps_str)


def generate_thumbnails(
    filepath: str,
    output_dir: str,
    interval: float = 1.0,
    thumb_height: int = 90,
) -> List[str]:
    """Generate thumbnail frames at regular intervals."""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-i", filepath,
        "-vf", f"scale=-1:{thumb_height},fps=1/{interval}",
        "-q:v", "4",
        "-start_number", "0",
        os.path.join(output_dir, "thumb_%04d.jpg"),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise FFmpegError(f"Thumbnail generation failed: {e}") from e
    if result.returncode != 0:
        raise FFmpegError(f"Thumbnail generation failed: {result.stderr}")

    files = sorted(
        f for f in os.listdir(output_dir) if f.startswith("thumb_") and f.endswith(".jpg")
    )
    return [os.path.join(output_dir, f) for f in files]


def export_segments(
    input_path: str,
    segments: List[Segment],
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """Export selected segments as a single video file."""
    if not segments:
        raise FFmpegError("No segments to export")

    tmpdir = tempfile.mkdtemp(prefix="vcut_")
    try:
        # Extract each segment
        for i, seg in enumerate(segments):
            seg_path = os.path.join(tmpdir, f"seg_{i:04d}.mkv")
            duration = seg.out_time - seg.in_time
            cmd = [
                "ffmpeg",
                "-ss", str(seg.in_time),
                "-i", input_path,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                seg_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise FFmpegError(f"Segment extraction failed: {result.stderr}")

        # Build file list for concat demuxer
        list_path = os.path.join(tmpdir, "concat_list.txt")
        with open(list_path, "w") as f:
            for i in range(len(segments)):
                f.write(f"file 'seg_{i:04d}.mkv'\n")

        # Concatenate all segments
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            "-y",
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise FFmpegError(f"Concatenation failed: {proc.stderr}")

        return output_path

    except Exception:
        _cleanup(tmpdir)
        raise
    else:
        _cleanup(tmpdir)


def has_audio_stream(input_path: str) -> bool:
    """Check whether the input file contains an audio stream."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", input_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    data = json.loads(result.stdout)
    return any(s.get("codec_type") == "audio" for s in data.get("streams", []))


def export_segments_reencode(
    input_path: str,
    segments: List[Segment],
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    codec: str = "libx264",
    audio_codec: str = "aac",
) -> str:
    """Export with re-encoding for better compatibility."""
    if not segments:
        raise FFmpegError("No segments to export")

    has_audio = has_audio_stream(input_path)
    n = len(segments)

    # Build complex filter for precise cutting and concatenation
    filter_parts = []
    video_refs = []
    audio_refs = []

    for i, seg in enumerate(segments):
        duration = seg.out_time - seg.in_time
        filter_parts.append(
            f"[0:v]trim=start={seg.in_time}:duration={duration},"
            f"setpts=PTS-STARTPTS[v{i}];"
        )
        video_refs.append(f"[v{i}]")

        if has_audio:
            filter_parts.append(
                f"[0:a]atrim=start={seg.in_time}:duration={duration},"
                f"asetpts=PTS-STARTPTS[a{i}];"
            )
            audio_refs.append(f"[a{i}]")

    # Concat video streams
    filter_parts.append(
        f"{''.join(video_refs)}concat=n={n}:v=1:a=0[vout];"
    )

    # Concat audio streams (if present)
    map_args = ["-map", "[vout]"]
    if has_audio:
        filter_parts.append(
            f"{''.join(audio_refs)}concat=n={n}:v=0:a=1[aout];"
        )
        map_args.extend(["-map", "[aout]"])

    full_filter = "".join(filter_parts)

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-filter_complex", full_filter,
    ] + map_args + [
        "-c:v", codec,
        "-crf", "23",
        "-preset", "medium",
    ]

    if has_audio:
        cmd.extend(["-c:a", audio_codec, "-b:a", "192k"])

    cmd.extend([
        "-movflags", "+faststart",
        "-y",
        output_path,
    ])

    _run_export_with_progress(cmd, sum(segment.duration for segment in segments), progress_callback)

    return output_path


def _run_export_with_progress(
    cmd: List[str], total_duration: float, progress_callback: Optional[Callable[[float], None]],
):
    progress_cmd = [cmd[0], "-v", "error", "-progress", "pipe:1", "-nostats"] + cmd[1:]
    try:
        proc = subprocess.Popen(
            progress_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as e:
        raise FFmpegError(f"Could not start ffmpeg: {e}") from e

    try:
        started = time.monotonic()
        assert proc.stdout is not None
        for line in proc.stdout:
            if time.monotonic() - started > 600:
                proc.kill()
                raise FFmpegError("Export timed out after 10 minutes")
            key, separator, value = line.strip().partition("=")
            if separator and key == "out_time_us" and progress_callback and total_duration > 0:
                try:
                    out_time = float(value)
                except ValueError:
                    continue
                progress_callback(min(out_time / 1_000_000 / total_duration, 0.99))
        stderr = proc.stderr.read() if proc.stderr else ""
        if proc.wait() != 0:
            raise FFmpegError(f"Export failed: {stderr}")
    except Exception:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        raise

    if progress_callback:
        progress_callback(1.0)


def _cleanup(path: str):
    import shutil
    try:
        shutil.rmtree(path)
    except Exception:
        pass
