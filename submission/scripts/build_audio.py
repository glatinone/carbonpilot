# Layer narration (TTS segments) into one timeline audio per video, then mux
# video (frames -> ffmpeg) + audio -> final MP4. Also patches gaps so the
# narration lands on the matching scene and the track fills the clip.
import os, subprocess, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUD = ROOT / "assets" / "audio"
FRAMES = ROOT / "frames"
OUT = ROOT  # videos land next to the one-pager

FFMPEG = "ffmpeg"

def dur(f):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "csv=p=0", str(f)],
        capture_output=True, text=True).stdout.strip())

def build(video_name, narration, scene_gap=1.6, end_pad=2.2, fps=24,
          width=1920, height=1080):
    """narration: ordered list of (tts_segment, scene_anchor_seconds).
    scene_anchor = start of the scenes in order (0, n1, n1+n2, ...)."""
    # ---- audio timeline: [nar at anchor .. anchor+dur], silence elsewhere
    filters, chain_in, chain_mix = [], [], []
    inputs = []
    for i, (seg, anchor) in enumerate(narration):
        f = AUD / seg
        d = dur(f)
        inputs.append(str(f))
        filters.append(f"[{i}:a]adelay={int(anchor*1000)}|{int(anchor*1000)}[d{i}]")
        chain_in.append(f"[d{i}]")
    fft = (";".join(filters) + ";" + "".join(chain_in)
           + f"amix=inputs={len(narration)}:normalize=0:dropout_transition=0[aud]")
    audio_out = str(HERE / f"{video_name}_audio.wav")
    subprocess.run([FFMPEG, "-y", *sum((["-i", s] for s in inputs), []),
                    "-filter_complex", fft, "-map", "[aud]", "-ar", "44100",
                    "-ac", "2", audio_out], check=True)

    # ---- video from frames at fps
    img_pattern = str(FRAMES / video_name / "f_%06d.png")
    vout = str(OUT / f"{video_name}_raw.mp4")
    subprocess.run([FFMPEG, "-y", "-framerate", str(fps),
                    "-i", img_pattern,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-vf",
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x14150F",
                    "-movflags", "+faststart", vout], check=True)

    # ---- mux
    fin = str(OUT / f"{video_name}.mp4")
    vd = dur(vout)
    subprocess.run([FFMPEG, "-y", "-i", vout, "-i", audio_out,
                    "-af", "apad=pad_dur=4",
                    "-t", f"{vd:.2f}",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0", fin], check=True)
    print("muxed:", fin, "v:", round(dur(vout),1), "a:", round(dur(audio_out),1))
    # cleanup intermediates
    Path(vout).unlink(missing_ok=True)
    Path(audio_out).unlink(missing_ok=True)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "explainer"
    if mode == "explainer":
        segs = ["n1.mp3", "n2.mp3", "n3.mp3", "n4.mp3", "n5.mp3", "n6.mp3", "n7.mp3"]
    else:
        segs = ["d1.mp3", "d2.mp3", "d3.mp3", "d4.mp3", "d5.mp3", "d6.mp3", "d7.mp3", "d8.mp3"]
    anchors = []
    t = 0.0
    for s in segs:
        anchors.append(t)
        t += dur(AUD / s) + 1.6
    build(mode, list(zip(segs, anchors)), fps=24)
    print(mode, "anchors:", [round(a, 1) for a in anchors], "total:", round(anchors[-1], 1))