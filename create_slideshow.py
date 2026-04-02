#!/usr/bin/env python3
"""
Slideshow-Generator: Bilder -> MP4 mit Ken-Burns-Effekten, Uebergaengen und optionaler Musik.
Aufruf: python create_slideshow.py --folder <pfad> [Optionen]
"""

import argparse
import os
import random
import re
import subprocess
import sys
import tempfile

# UTF-8 stdout - verhindert UnicodeEncodeError auf Windows-Konsolen (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import imageio
import numpy as np
from PIL import Image

EFFECTS = ["zoom_in", "zoom_out", "pan_right", "pan_left", "zoom_pan"]
TRANSITIONS = ["crossfade", "fade_black", "wipe_right"]
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
SUPPORTED_AUDIO_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma"}


# ── Bild-Hilfsfunktionen ───────────────────────────────────────────────────────

def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def prepare_image(path: str, W: int, H: int, margin: float = 1.3) -> Image.Image:
    img = Image.open(path).convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = W / H

    if img_ratio >= target_ratio:
        scale = max(W * margin / img.width, H * margin / img.height)
        return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    else:
        scale = min(W / img.width, H / img.height)
        scaled = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas.paste(scaled, ((W - scaled.width) // 2, (H - scaled.height) // 2))
        return canvas.resize((int(W * margin), int(H * margin)), Image.LANCZOS)


def get_crop(img: Image.Image, t: float, W: int, H: int, effect: str) -> np.ndarray:
    p = smoothstep(t)
    iw, ih = img.size
    aspect = W / H

    if effect == "zoom_in":
        crop_frac = 1.0 - 0.2 * p
    elif effect == "zoom_out":
        crop_frac = 0.8 + 0.2 * p
    else:
        crop_frac = 0.85

    cw = int(iw * crop_frac)
    ch = int(cw / aspect)
    if ch > ih:
        ch = ih
        cw = int(ch * aspect)
    if cw > iw:
        cw = iw
        ch = int(cw / aspect)

    max_cx = max(0, iw - cw)
    max_cy = max(0, ih - ch)

    if effect in ("zoom_in", "zoom_out"):
        cx, cy = max_cx // 2, max_cy // 2
    elif effect == "pan_right":
        cx, cy = int(max_cx * p), max_cy // 2
    elif effect == "pan_left":
        cx, cy = int(max_cx * (1.0 - p)), max_cy // 2
    elif effect == "zoom_pan":
        cx, cy = int(max_cx * p), int(max_cy * p)
    else:
        cx, cy = max_cx // 2, max_cy // 2

    cx = max(0, min(cx, max_cx))
    cy = max(0, min(cy, max_cy))
    cropped = img.crop((cx, cy, cx + cw, cy + ch))
    return np.array(cropped.resize((W, H), Image.LANCZOS), dtype=np.uint8)


def blend(frame_a: np.ndarray, frame_b: np.ndarray, t: float) -> np.ndarray:
    return (frame_a * (1.0 - t) + frame_b * t).astype(np.uint8)


def transition_frames(frame_a, frame_b, n_frames, transition):
    _, W = frame_a.shape[:2]
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        if transition == "crossfade":
            yield blend(frame_a, frame_b, t)
        elif transition == "fade_black":
            if t < 0.5:
                yield (frame_a * (1.0 - t * 2.0)).astype(np.uint8)
            else:
                yield (frame_b * ((t - 0.5) * 2.0)).astype(np.uint8)
        elif transition == "wipe_right":
            split = int(W * t)
            frame = frame_a.copy()
            if split > 0:
                frame[:, :split] = frame_b[:, :split]
            yield frame
        else:
            yield blend(frame_a, frame_b, t)


def collect_images(folder: str, sort_mode: str) -> list:
    files = [
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXT
    ]
    if not files:
        raise RuntimeError(f"Keine Bilder in '{folder}' gefunden.")
    if sort_mode == "name":
        files.sort(key=lambda p: os.path.basename(p).lower())
    elif sort_mode == "date":
        files.sort(key=lambda p: os.path.getmtime(p))
    elif sort_mode == "random":
        random.shuffle(files)
    return files


# ── Musik-Hilfsfunktionen ──────────────────────────────────────────────────────

def get_ffmpeg_exe() -> str:
    """Gibt den Pfad zum ffmpeg-Binary zurueck (via imageio-ffmpeg)."""
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def get_audio_duration(ffmpeg_exe: str, filepath: str):
    result = subprocess.run(
        [ffmpeg_exe, "-i", filepath],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return None


def collect_audio(folder: str, sort_mode: str) -> list:
    files = [
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in SUPPORTED_AUDIO_EXT
    ]
    if sort_mode == "name":
        files.sort(key=lambda p: os.path.basename(p).lower())
    elif sort_mode == "date":
        files.sort(key=lambda p: os.path.getmtime(p))
    elif sort_mode == "random":
        random.shuffle(files)
    return files


def build_audio_track(audio_files, total_duration, transition, trans_dur,
                       volume, loop, ffmpeg_exe, output_audio, log=print) -> bool:
    log(f"\nMusik: {len(audio_files)} Datei(en) gefunden.")

    tracks = []
    for f in audio_files:
        dur = get_audio_duration(ffmpeg_exe, f)
        if dur is None:
            log(f"  Warnung: Dauer von '{os.path.basename(f)}' nicht ermittelbar - uebersprungen.")
            continue
        tracks.append((f, dur))
        log(f"  {os.path.basename(f):40s}  {dur:.1f}s")

    if not tracks:
        log("  Fehler: Keine verwertbaren Audiodateien.")
        return False

    if loop:
        def total_audio_dur(lst):
            s = sum(d for _, d in lst)
            if transition == "crossfade" and len(lst) > 1:
                s -= trans_dur * (len(lst) - 1)
            return s

        extended = list(tracks)
        while total_audio_dur(extended) < total_duration:
            for item in tracks:
                extended.append(item)
                if total_audio_dur(extended) >= total_duration:
                    break
        tracks = extended
        log(f"  Loop: Playlist auf {len(tracks)} Tracks erweitert.")

    n = len(tracks)
    cmd = [ffmpeg_exe, "-y"]
    for f, _ in tracks:
        cmd += ["-i", f]

    filter_parts = []

    if transition == "none":
        inputs = "".join(f"[{i}:a]" for i in range(n))
        filter_parts.append(f"{inputs}concat=n={n}:v=0:a=1[acat]")
        last = "acat"

    elif transition == "crossfade":
        td = min(trans_dur, *(d / 2 for _, d in tracks))
        if n == 1:
            filter_parts.append("[0:a]anull[acat]")
            last = "acat"
        else:
            filter_parts.append(f"[0:a][1:a]acrossfade=d={td:.3f}:c1=tri:c2=tri[ac0]")
            for i in range(2, n):
                prev, cur = f"ac{i - 2}", f"ac{i - 1}"
                filter_parts.append(f"[{prev}][{i}:a]acrossfade=d={td:.3f}:c1=tri:c2=tri[{cur}]")
            last = f"ac{n - 2}"

    elif transition == "fadeout":
        for i, (_, dur) in enumerate(tracks):
            fd = min(trans_dur, dur / 2)
            filter_parts.append(f"[{i}:a]afade=t=out:st={max(0.0, dur-fd):.3f}:d={fd:.3f}[af{i}]")
        inputs = "".join(f"[af{i}]" for i in range(n))
        filter_parts.append(f"{inputs}concat=n={n}:v=0:a=1[acat]")
        last = "acat"

    elif transition == "fadeinout":
        for i, (_, dur) in enumerate(tracks):
            fd = min(trans_dur, dur / 3)
            parts = []
            if i > 0:
                parts.append(f"afade=t=in:st=0:d={fd:.3f}")
            parts.append(f"afade=t=out:st={max(0.0, dur-fd):.3f}:d={fd:.3f}")
            filter_parts.append(f"[{i}:a]{','.join(parts)}[af{i}]")
        inputs = "".join(f"[af{i}]" for i in range(n))
        filter_parts.append(f"{inputs}concat=n={n}:v=0:a=1[acat]")
        last = "acat"

    else:
        inputs = "".join(f"[{i}:a]" for i in range(n))
        filter_parts.append(f"{inputs}concat=n={n}:v=0:a=1[acat]")
        last = "acat"

    filter_parts.append(f"[{last}]volume={volume:.3f}[avol]")
    filter_parts.append(
        f"[avol]atrim=duration={total_duration:.3f},asetpts=PTS-STARTPTS[atrim]"
    )
    last = "atrim"

    if total_duration > 5:
        filter_parts.append(
            f"[{last}]afade=t=out:st={max(0.0, total_duration-2.0):.3f}:d=2[afinal]"
        )
        last = "afinal"

    cmd += [
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{last}]",
        "-c:a", "aac", "-b:a", "192k",
        output_audio,
    ]

    log(f"  Audioverarbeitung ({transition}) ...")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        log(f"  ffmpeg-Fehler:\n{result.stderr[-600:]}")
        return False
    return True


def merge_audio_video(video_path, audio_path, output_path, ffmpeg_exe, log=print) -> bool:
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
        output_path,
    ]
    log("  Zusammenfuehren von Video und Audio ...")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        log(f"  ffmpeg-Fehler:\n{result.stderr[-600:]}")
        return False
    return True


# ── Kernlogik (aufrufbar ohne CLI) ────────────────────────────────────────────

def run(args_ns, log=print, cancel_event=None) -> bool:
    """
    Fuehrt die Slideshow-Generierung durch.

    args_ns      : argparse.Namespace mit allen Optionen
    log          : callable(str) fuer Ausgaben (thread-sicher nutzen)
    cancel_event : threading.Event – wird auf .is_set() geprueft

    Gibt True bei Erfolg, False bei Abbruch zurueck.
    Wirft RuntimeError bei Konfigurationsfehlern.
    """
    def cancelled():
        return cancel_event is not None and cancel_event.is_set()

    W   = args_ns.width
    H   = args_ns.height
    fps = args_ns.fps
    n_frames = int(args_ns.duration * fps)
    n_trans  = int(args_ns.transition * fps)

    folder = os.path.abspath(args_ns.folder)
    if not os.path.isdir(folder):
        raise RuntimeError(f"Ordner '{folder}' nicht gefunden.")

    images = collect_images(folder, args_ns.sort)
    log(f"{len(images)} Bild(er) gefunden in: {folder}")
    log(f"Ausgabe: {args_ns.output}  |  {W}x{H}  |  {fps} fps  |  "
        f"{args_ns.duration}s/Bild  |  {args_ns.transition}s Uebergang")
    log("")

    quality_map = {1: 28, 2: 26, 3: 24, 4: 22, 5: 20, 6: 18, 7: 16, 8: 14, 9: 12, 10: 10}
    crf = quality_map.get(args_ns.quality, 14)

    use_music = bool(
        getattr(args_ns, "music_folder", None)
        and args_ns.music_folder
        and os.path.isdir(args_ns.music_folder)
    )

    if use_music:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_target = tmp.name
        tmp.close()
    else:
        video_target = args_ns.output

    writer = imageio.get_writer(
        video_target,
        fps=fps,
        codec="libx264",
        output_params=["-crf", str(crf)],
        macro_block_size=None,
    )

    prev_last_frame = None
    total_video_duration = 0.0
    aborted = False

    try:
        for i, path in enumerate(images):
            if cancelled():
                aborted = True
                break

            line = f"  [{i+1}/{len(images)}] {os.path.basename(path)}"
            img    = prepare_image(path, W, H)
            effect = random.choice(EFFECTS)
            trans  = random.choice(TRANSITIONS)
            line += f"  ({effect})"

            if prev_last_frame is not None:
                first_frame_b = get_crop(img, 0.0, W, H, effect)
                for fr in transition_frames(prev_last_frame, first_frame_b, n_trans, trans):
                    if cancelled():
                        aborted = True
                        break
                    writer.append_data(fr)
                if aborted:
                    break
                total_video_duration += args_ns.transition
                line += f" -> {trans}"

            for frame_idx in range(n_frames):
                if cancelled():
                    aborted = True
                    break
                t = frame_idx / max(n_frames - 1, 1)
                writer.append_data(get_crop(img, t, W, H, effect))
            if aborted:
                break

            total_video_duration += args_ns.duration
            prev_last_frame = get_crop(img, 1.0, W, H, effect)
            log(line)

    finally:
        writer.close()

    if aborted:
        log("Abgebrochen.")
        try:
            os.unlink(video_target)
        except OSError:
            pass
        return False

    log("")
    log(f"Videolaenge: {total_video_duration:.1f}s")

    # Musik hinzufuegen
    if use_music:
        audio_files = collect_audio(args_ns.music_folder,
                                    getattr(args_ns, "music_sort", "name"))
        if not audio_files:
            log(f"Warnung: Keine Audiodateien gefunden - ohne Musik.")
            os.replace(video_target, args_ns.output)
        else:
            ffmpeg_exe = get_ffmpeg_exe()
            tmp_audio = tempfile.NamedTemporaryFile(suffix=".aac", delete=False)
            tmp_audio.close()

            ok = build_audio_track(
                audio_files,
                total_video_duration,
                getattr(args_ns, "music_transition", "crossfade"),
                getattr(args_ns, "music_transition_duration", 2.0),
                getattr(args_ns, "music_volume", 1.0),
                getattr(args_ns, "music_loop", False),
                ffmpeg_exe,
                tmp_audio.name,
                log=log,
            )

            if ok:
                ok2 = merge_audio_video(video_target, tmp_audio.name,
                                        args_ns.output, ffmpeg_exe, log=log)
                if not ok2:
                    log("Fehler beim Zusammenfuehren - Video ohne Musik gespeichert.")
                    os.replace(video_target, args_ns.output)
            else:
                log("Fehler bei Audioverarbeitung - Video ohne Musik gespeichert.")
                os.replace(video_target, args_ns.output)

            for tmp_path in [video_target, tmp_audio.name]:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    log("")
    log(f"Fertig! Datei gespeichert: {os.path.abspath(args_ns.output)}")
    return True


# ── CLI-Einstiegspunkt ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Erstellt eine MP4-Slideshow mit Ken-Burns-Effekten aus einem Bildordner."
    )
    parser.add_argument("--folder",     required=True)
    parser.add_argument("--output",     default="slideshow.mp4")
    parser.add_argument("--duration",   type=float, default=5.0)
    parser.add_argument("--transition", type=float, default=1.2)
    parser.add_argument("--fps",        type=int,   default=25)
    parser.add_argument("--width",      type=int,   default=1920)
    parser.add_argument("--height",     type=int,   default=1080)
    parser.add_argument("--sort",       default="name", choices=["name", "date", "random"])
    parser.add_argument("--quality",    type=int,   default=8)
    parser.add_argument("--music-folder",              default=None)
    parser.add_argument("--music-sort",                default="name",
                        choices=["name", "date", "random"])
    parser.add_argument("--music-transition",          default="crossfade",
                        choices=["none", "crossfade", "fadeout", "fadeinout"])
    parser.add_argument("--music-transition-duration", type=float, default=2.0)
    parser.add_argument("--music-volume",              type=float, default=1.0)
    parser.add_argument("--music-loop",                action="store_true")

    args = parser.parse_args()
    try:
        result = run(args)
    except RuntimeError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
    if not result:
        sys.exit(0)


if __name__ == "__main__":
    main()
