#!/usr/bin/env python3
"""
Render a cut list (EDL from edl.py) into a finished, captioned video and its .srt.

Video: decode each cut at 30 fps -> camera-shake stabilisation + face/mouth-aware crop and zoom
       (one sub-pixel affine per frame) -> grade + burned-in captions -> H.264.
Audio: each cut from the cleaned edit track, cut to the exact frame count, 12/18 ms edge fades,
       concatenated, voice chain + loudness, faded out after the last word.

Needs, per source in the EDL: clean/edit/<src>.wav, transcripts/<src>.final.json,
tracking/<src>.faces.json (faces.py) and tracking/<src>.camera.json (camtrack.py).

Usage:
  python3 render.py EDL_NAME [--project DIR] [--preview] [--kind shorts|long] [--hash-frames]

  --preview       fast encode (veryfast, CRF 24) for checking cuts; masters use slow, CRF 17
  --kind          output subfolder; default: shorts for 9x16, long for 4x5
  --hash-frames   also write work/<name>/frames.sha256 (for parity tests)

Output: <output_dir>/<kind>/<name>.mp4 and .srt, replaced only after the new render's frame count checks out;
intermediates in work/<name>/.
Exit 0 = rendered and frame count verified. Exit 2 = refused (missing inputs). Exit 1 = a step failed.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

vc.require(["numpy", "cv2"], vc.VENV_CV)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

import camtrack  # noqa: E402
import vnum  # noqa: E402
from captions import build_ass, build_srt  # noqa: E402

FPS = vc.FPS
HORIZONTAL_FACE_BAND = 0.3     # face centre kept within the middle 40% of the frame width
# Phone video has slightly irregular frame timing, so a seek can land one frame away from the frame the camera
# path was measured on; the correction then adds shake instead of removing it. Each cut's first frames are
# matched against the path to find the true offset.
OFFSET_PROBE_FRAMES = 24
OFFSET_SEARCH = 2
OFFSET_CLEAR_RATIO = 0.5       # the best offset's error must be under half the next best, else keep 0
FACE_DESPIKE_S = 0.5           # rolling-median window that removes single-sample face detection glitches
DECODE_TAIL_S = 0.2            # extra seconds decoded past a cut so rounding never starves the last frame
MAX_REPEATED_FRAMES = 2        # a cut may reuse its last decoded frame this often (rounding at a file's end)
END_FADE_MIN_ROOM_S = 0.05     # skip the ending fade when the last word ends this close to the cut's end
STAB_MARGIN_EXTRA_PX = 4       # added to the measured shake when reserving crop margin
CAPTION_SIZE_MEASURED = 100    # vc.CAP_HALF was measured at this caption size; clearance scales from it


class Source:
    """Per-source stabilisation and framing tracks, all at 30 fps on the source timeline."""

    def __init__(self, proj: vc.Project, sid: str):
        self.sid = sid
        self.file = proj.source_file(sid)
        self.SW, self.SH = proj.source_size(sid)
        if self.SW > self.SH:
            vc.die(f"Source {sid} is landscape ({self.SW}x{self.SH}); only portrait sources are supported so far.", 2)
        for need, fix in ((proj.clean_edit(sid), "clean_audio.py"), (proj.final_words(sid), "align.py + fix_words.py"),
                          (proj.faces(sid), "faces.py"), (proj.camtrack(sid), "camtrack.py")):
            if not need.is_file():
                vc.die(f"Missing {need.relative_to(proj.root)} for source {sid}. Run {fix} first.", 2)
        self.audio = proj.clean_edit(sid)
        self.words = json.loads(proj.final_words(sid).read_text())
        self._tracks(proj)

    def _tracks(self, proj: vc.Project) -> None:
        SW, SH = self.SW, self.SH
        cam = np.array(json.loads(proj.camtrack(self.sid).read_text())["traj"], float)
        self.inc = np.diff(cam, axis=0)        # per-frame motion as measured, for frame_offset()
        cam = vnum.centre_path(cam, SW, SH)
        self.corr = np.stack([vnum.gaussian(cam[:, c], vc.CAM_SIGMA_S * FPS) - cam[:, c] for c in range(3)], 1)
        d = json.loads(proj.faces(self.sid).read_text())
        fs = d["fps_sample"]
        arr = np.array([[s[0]] + [np.nan if v is None else v for v in s[1:4]] for s in d["samples"]], float)
        t = arr[:, 0]
        self.tt = np.arange(len(cam)) / FPS
        face = []
        for c in (1, 2, 3):
            v = arr[:, c]
            ok = ~np.isnan(v)
            if not ok.any():
                vc.die(f"No face was detected anywhere in source {self.sid}; framing needs a visible face.", 2)
            v = np.interp(t, t[ok], v[ok])
            k = int(fs * FACE_DESPIKE_S) | 1
            pad = np.pad(v, k // 2, mode="edge")
            v = np.array([np.median(pad[i:i + k]) for i in range(len(v))])
            face.append(np.interp(self.tt, t, v))
        fxr, fyr, fwr = face
        corr = self.corr
        ca, sa = np.cos(corr[:, 2]), np.sin(corr[:, 2])
        fxs = ca * (fxr - SW / 2) - sa * (fyr - SH / 2) + SW / 2 + corr[:, 0]
        fys = sa * (fxr - SW / 2) + ca * (fyr - SH / 2) + SH / 2 + corr[:, 1]
        # conservative lip path: rolling max of the unsmoothed lower-lip estimate, then a gaussian whose support
        # stays inside that window, so it is never above the true mouth (quick head dips)
        mouth = fys + vc.MOUTH_K * fwr
        half = int(vc.MOUTH_ENVELOPE_S * FPS)
        rmax = np.array([mouth[max(0, k - half):k + half + 1].max() for k in range(len(mouth))])
        self.mouth_env = vnum.gaussian(rmax, half / 3)
        self.fx = vnum.gaussian(fxs, vc.FACE_SIGMA_S * FPS)
        self.fy = vnum.gaussian(fys, vc.FACE_SIGMA_S * FPS)
        self.fw = vnum.gaussian(fwr, vc.FACE_SIGMA_S * FPS)

    def frame_offset(self, start: float, n: int) -> int:
        """Frames between where a decode seeked to `start` begins and where the camera path says it should."""
        m = min(n, OFFSET_PROBE_FRAMES)
        sw, sh = self.SW // camtrack.DECODE_DIVISOR, self.SH // camtrack.DECODE_DIVISOR
        p = subprocess.Popen(camtrack.decode_args(self.file, self.SW, self.SH, start, m / FPS + DECODE_TAIL_S),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frames = []
        while len(frames) < m:
            buf = p.stdout.read(sw * sh)
            if len(buf) < sw * sh:
                break
            frames.append(np.frombuffer(buf, np.uint8).reshape(sh, sw))
        p.stdout.close()
        p.wait()   # closed early on purpose
        k = self.SW / sw
        motion = [camtrack.pair_motion(a, b, k) for a, b in zip(frames, frames[1:])]
        measured = np.array([(d[0], d[1]) if d else (np.nan, np.nan) for d in motion])
        if len(measured) < 5:
            return 0
        j0 = int(round(start * FPS))
        errs = {}
        for off in range(-OFFSET_SEARCH, OFFSET_SEARCH + 1):
            a = j0 + off
            if a < 0 or a + len(measured) > len(self.inc):
                continue
            e = np.hypot(*(self.inc[a:a + len(measured), :2] - measured).T)
            e = e[~np.isnan(e)]
            if len(e):
                errs[off] = float(np.median(e))
        if len(errs) < 2:
            return 0
        ranked = sorted(errs, key=errs.get)
        best, second = ranked[0], ranked[1]
        return best if errs[best] < OFFSET_CLEAR_RATIO * errs[second] else 0

    def stab_matrix(self, dx: float, dy: float, da: float) -> np.ndarray:
        SW, SH = self.SW, self.SH
        c, s_ = np.cos(da), np.sin(da)
        return np.array([[c, -s_, SW / 2 - c * SW / 2 + s_ * SH / 2 + dx],
                         [s_, c, SH / 2 - s_ * SW / 2 - c * SH / 2 + dy],
                         [0, 0, 1]], float)


def frames_of(seg: dict) -> int:
    return int(round((seg["out"] - seg["in"]) * FPS))


def render(proj: vc.Project, edl: dict, kind: str | None, preview: bool, hash_frames: bool) -> Path:
    fmt = vc.FORMATS[edl["format"]]
    OW, OH = fmt["size"]
    Z0, FACE_Y, CAP_Y = fmt["base_zoom"], fmt["face_y"], fmt["caption_y"]
    name = edl["name"]
    kind = kind or ("long" if edl["format"] == "4x5" else "shorts")
    work = proj.work(name, create=True)
    (work / "framing.json").unlink(missing_ok=True)   # QA refuses until this render succeeds (intermediates get replaced)
    out_dir = proj.output_dir(kind)
    sources = {s: Source(proj, s) for s in sorted({seg["src"] for seg in edl["segments"]})}
    for r in edl.get("retext", []):
        hit = [w for w in sources[r["src"]].words if abs(w["s"] - r["s"]) < 1e-3]
        if len(hit) != 1:
            vc.die(f"retext for {r['src']} at {r['s']}s matched {len(hit)} words; rebuild the EDL with edl.py.", 2)
        hit[0]["w"] = r["w"]

    # ---- timeline: caption words and per-cut audio
    t_out, cap_words, wavs = 0.0, [], []
    for i, seg in enumerate(edl["segments"]):
        n = frames_of(seg)
        dur = n / FPS
        for w in sources[seg["src"]].words:
            mid = (w["s"] + w["e"]) / 2
            if seg["in"] <= mid < seg["in"] + dur:
                cap_words.append({"w": w["w"], "s": max(0.0, w["s"] - seg["in"]) + t_out,
                                  "e": min(dur, w["e"] - seg["in"]) + t_out, "seg": i})
        wav = work / f"a{i:03d}.wav"
        vc.ffmpeg(["-ss", f"{seg['in']:.3f}", "-i", sources[seg["src"]].audio, "-t", f"{dur:.4f}", "-vn", "-ac", "2",
                   "-ar", str(vc.AUDIO_RATE), "-af",
                   f"apad,atrim=0:{dur:.4f},afade=t=in:d={vc.FADE_IN_S},afade=t=out:st={dur - vc.FADE_OUT_S:.4f}:d={vc.FADE_OUT_S}",
                   wav], f"Cutting audio for cut {i + 1}")
        wavs.append(wav)
        t_out += dur
    total = t_out
    total_frames = sum(frames_of(seg) for seg in edl["segments"])
    for i, w in enumerate(cap_words):   # a new cut is a real pause in delivery: start a new caption phrase
        w["brk"] = i > 0 and w["seg"] != cap_words[i - 1]["seg"]
    for i, w in enumerate(cap_words):   # sentence case: the first word and anything after . ? !
        if i == 0 or cap_words[i - 1]["w"][-1] in ".?!":
            w["w"] = w["w"][:1].upper() + w["w"][1:]

    last_i = len(edl["segments"]) - 1
    last_words = [w for w in cap_words if w["seg"] == last_i]
    if last_words:   # the held beat after the last word ends in silence
        seg_start = total - frames_of(edl["segments"][-1]) / FPS
        fade_st = last_words[-1]["e"] - seg_start + vc.END_FADE_AFTER_WORD_S
        last_dur = frames_of(edl["segments"][-1]) / FPS
        if fade_st < last_dur - END_FADE_MIN_ROOM_S:
            tmp = wavs[-1].with_suffix(".fade.wav")
            vc.ffmpeg(["-i", wavs[-1], "-af", f"afade=t=out:st={fade_st:.3f}:d={min(vc.END_FADE_MAX_S, last_dur - fade_st):.3f}",
                       tmp], "Fading out the ending")
            os.replace(tmp, wavs[-1])

    lst = work / "audio.txt"
    lst.write_text("".join(vc.concat_line(w) for w in wavs))
    audio = work / "audio.wav"
    # exact sample count = frames x samples-per-frame; never -t here (loudnorm shifts timestamps, -t drops the tail)
    vc.ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-af",
               f"{vc.VOICE_CHAIN},atrim=end_sample={total_frames * vc.SAMPLES_PER_FRAME}", audio], "Finishing the audio")

    pill = edl.get("lower_third")
    if not pill and proj.cfg["name_pill"].get("text"):
        pill = [proj.cfg["name_pill"]["text"], proj.cfg["name_pill"].get("title", "")]
    lt = (pill[0], pill[1], *vc.NAME_PILL_SECONDS, vc.NAME_PILL_X, CAP_Y - vc.NAME_PILL_ABOVE_CAPTION) if pill else None
    cap = proj.cfg["captions"]
    ass = work / "captions.ass"
    ass.write_text(build_ass(cap_words, OW, OH, CAP_Y, font=cap["font"], size=cap["size"],
                             hi=vc.ass_colour(cap["highlight"]), name_pill=lt))
    srt_text = build_srt(cap_words)
    (work / "cap_words.json").write_text(json.dumps(cap_words, indent=0))

    # ---- video
    out_mp4 = out_dir / f"{name}.mp4"
    partial_mp4 = out_dir / f"{name}.partial.mp4"      # renamed only after the frame count checks out
    atexit.register(partial_mp4.unlink, missing_ok=True)
    vf = f"{vc.GRADE},subtitles={vc.filter_path(ass)}:fontsdir={vc.filter_path(vc.FONTS_DIR)},format=yuv420p"
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
                            "-i", str(audio), "-map", "0:v", "-map", "1:a", "-vf", vf,
                            "-c:v", "libx264", "-preset", "veryfast" if preview else "slow", "-crf", "24" if preview else "17",
                            "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:a", "aac", "-b:a", "192k", "-map_metadata", "-1", "-movflags", "+faststart",
                            str(partial_mp4)], stdin=subprocess.PIPE)   # no -shortest: it dropped the last frame
    fh = hashlib.sha256() if hash_frames else None
    cap_half = vc.CAP_HALF * cap["size"] / CAPTION_SIZE_MEASURED
    L = CAP_Y - cap_half - vc.MOUTH_CLEAR      # lowest allowed lip y in output px
    framing = []                               # per-cut zoom actually used; shake_metric.py reads it
    for i, seg in enumerate(edl["segments"]):
        S = sources[seg["src"]]
        SW, SH = S.SW, S.SH
        n = frames_of(seg)
        fx, fy, fw, mouth_env, corr, tt = S.fx, S.fy, S.fw, S.mouth_env, S.corr, S.tt
        # framing for this cut (per-frame placement below):
        # 1) punch-ins may not push the face past FACE_MAX_FRAC of the frame width
        # 2) the lip must be placeable above the captions, which sets a minimum zoom
        # 3) never above Z_MAX
        a, b = int(seg["in"] * FPS), int(seg["in"] * FPS) + n
        mcx = float(np.median(fx[a:b]))
        fw90 = float(np.percentile(fw[a:b], 90))
        mouth90 = float(np.percentile(mouth_env[a:b], 90))
        z = min(Z0 * seg.get("zoom", 1.0), max(Z0, vc.FACE_MAX_FRAC * SW / fw90))
        ww_mouth = max(1.0, (SH - mouth90)) * OW / (OH - L)
        ww_h = min(mcx / HORIZONTAL_FACE_BAND, (SW - mcx) / HORIZONTAL_FACE_BAND, SW)
        z_need = max(SW / ww_mouth, SW / ww_h)
        z_final = min(max(z, z_need), vc.Z_MAX)
        if abs(z_final - Z0 * seg.get("zoom", 1.0)) > 1e-3:
            print(f"  cut {i + 1}: zoom {Z0 * seg.get('zoom', 1.0):.2f} -> {z_final:.2f} "
                  f"(face w90 {fw90:.0f}, lip90 {mouth90:.0f}, need {z_need:.2f})")
        z = z_final
        if OW / OH < SW / SH:
            wh = SH / z
            ww = wh * OW / OH
        else:
            ww = SW / z
            wh = ww * OH / OW
        # plan the whole cut before decoding: reserve a stabilisation margin, then find the largest shake
        # correction per frame that keeps frame edges out of the crop, smoothed so it can't add jitter
        off = S.frame_offset(seg["in"], n)
        J = np.clip(np.round((seg["in"] + np.arange(n) / FPS) * FPS).astype(int) + off, 0, len(tt) - 1)
        cj = corr[J]
        half_diag = np.hypot(ww, wh) / 2
        need = np.percentile(np.hypot(cj[:, 0], cj[:, 1]), 95) + np.percentile(np.abs(cj[:, 2]), 95) * half_diag + STAB_MARGIN_EXTRA_PX
        mx, my = min((SW - ww) / 2, need), min((SH - wh) / 2, need)
        sc = OW / ww
        X0 = np.clip(fx[J] - ww / 2, mx, SW - ww - mx)
        # face at FACE_Y, raised further when the lip needs it; lip clearance outranks the stabilisation margin
        Y0_mouth = mouth_env[J] - L / sc
        Y0 = np.maximum(fy[J] - wh * FACE_Y, Y0_mouth)
        y_hi = np.where(Y0_mouth > SH - wh - my, SH - wh - 2, SH - wh - my)
        Y0 = np.clip(Y0, my, y_hi)
        corners = np.array([[0, OW, 0, OW], [0, 0, OH, OH], [1, 1, 1, 1]], float)

        def _mats(k: int, kk: float) -> np.ndarray:
            C = np.array([[sc, 0, -X0[k] * sc], [0, sc, -Y0[k] * sc], [0, 0, 1]], float)
            return C @ S.stab_matrix(*(cj[k] * kk))

        def _inside(M: np.ndarray) -> bool:
            q = np.linalg.inv(M) @ corners
            return q[0].min() >= 0 and q[0].max() <= SW - 1 and q[1].min() >= 0 and q[1].max() <= SH - 1

        kmax = np.ones(n)
        for k in range(n):
            if not _inside(_mats(k, 1.0)):
                lo, hi = 0.0, 1.0
                for _ in range(10):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if _inside(_mats(k, mid)) else (lo, mid)
                kmax[k] = lo
        W8 = vc.KK_WINDOW
        rmin = np.array([kmax[max(0, k - W8):k + W8 + 1].min() for k in range(n)])
        kk_arr = np.minimum(vnum.gaussian(rmin, W8 / 3), kmax) if n > 1 else rmin
        clamped = int((kk_arr < 0.999).sum())
        dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{seg['in']:.3f}",
                                "-i", str(S.file), "-t", f"{n / FPS + DECODE_TAIL_S:.4f}", "-vf", f"fps={FPS}",
                                "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        last, short = None, 0
        for k in range(n):
            buf = dec.stdout.read(SW * SH * 3)
            if len(buf) == SW * SH * 3:
                last = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            else:
                short += 1
                if last is None or short > MAX_REPEATED_FRAMES:
                    dec.kill()
                    enc.kill()
                    vc.die(f"Cut {i + 1} ({S.sid} {seg['in']:.2f}-{seg['out']:.2f}s): the source ran out of frames "
                           f"after {k - short + 1} of {n}. The cut goes past the end of the recording or the file is "
                           "damaged; fix the spec (edl.py) or check the source. Any earlier finished video is untouched.")
            M = _mats(k, kk_arr[k])
            outf = cv2.warpAffine(last, M[:2].astype(np.float32), (OW, OH), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
            data = outf.tobytes()
            if fh:
                fh.update(data)
            try:
                enc.stdin.write(data)
            except BrokenPipeError:
                dec.kill()
                vc.die(f"The video encoder stopped early (exit {enc.wait()}); its error is printed above.")
        dec.stdout.close()
        dec.wait()   # closed early on purpose once n frames are read; its exit status is not meaningful
        framing.append({"src": S.sid, "in": seg["in"], "frames": n, "zoom": round(float(z), 4),
                        "scale": round(float(sc), 6), "eased_frames": clamped, "source_size": [SW, SH],
                        "frame_offset": off})
        note = f"  (shake correction eased on {clamped}/{n} frames)" if clamped else ""
        if off:
            note += f"  (decode {off:+d} frame vs camera path, corrected)"
        if short:
            note += f"  (repeated the last frame {short}x at the end of the source)"
        print(f"  cut {i + 1}/{len(edl['segments'])} {S.sid} {seg['in']:.2f}-{seg['out']:.2f} z={z:.2f}{note}", flush=True)
    enc.stdin.close()
    vc.check_wait(enc, "Encoding the video")
    got = vc.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                  "stream=nb_read_frames", "-of", "csv=p=0", str(partial_mp4)], "Counting output frames").stdout.strip()
    if got != str(total_frames):
        vc.die(f"{name}: expected {total_frames} frames, got {got}. Not delivered; any earlier finished video is "
               "untouched.")
    os.replace(partial_mp4, out_mp4)
    vc.write_atomic(out_dir / f"{name}.srt", srt_text)
    vc.write_atomic(work / "framing.json", json.dumps({"format": edl["format"], "output": str(out_mp4),
                                                       "cuts": framing}, indent=1))
    if fh:
        (work / "frames.sha256").write_text(fh.hexdigest() + "\n")
    print(f"done {out_mp4} {total:.2f}s, {total_frames} frames verified")
    return out_mp4


def main() -> None:
    ap = argparse.ArgumentParser(description="Render an EDL into a captioned video.")
    ap.add_argument("edl", help="EDL name (edls/NAME.json) or a path")
    ap.add_argument("--project")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--kind", choices=["shorts", "long"])
    ap.add_argument("--hash-frames", action="store_true")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    p = Path(args.edl) if args.edl.endswith(".json") else proj.edl(args.edl)
    if not p.is_file():
        vc.die(f"EDL {p} not found. Build it with edl.py.", 2)
    for binary in ("ffmpeg", "ffprobe"):
        vc.need_binary(binary, "Install ffmpeg (see doctor.py).")
    edl = json.loads(p.read_text())
    font = proj.cfg["captions"]["font"]
    needed = [(font, "ExtraBold")]
    if edl.get("lower_third") or proj.cfg["name_pill"].get("text"):
        needed += [("Inter", "SemiBold"), ("Inter", "Medium")]
    for family, weight in needed:
        if not any(vc.FONTS_DIR.glob(f"{family.replace(' ', '')}*{weight}*.[ot]tf")):
            vc.die(f"Font {family} {weight} not found in {vc.FONTS_DIR}. Run setup_toolkit.py fonts, or for another "
                   f"caption font add its {weight} file there (named like {family.replace(' ', '')}-{weight}.ttf). "
                   "Without it captions silently fall back to a different font.", 2)
    render(proj, edl, args.kind, args.preview, args.hash_frames)


if __name__ == "__main__":
    main()
