#!/usr/bin/env python3
"""
Numeric helpers shared by the video stages (numpy). Library module; not run directly.

Kept in one place because two of these fixed real bugs and must not drift between
the renderer and the QA that measures it:
  * centre_path(): per-frame camera motion re-expressed at the image centre. Motion
    measured at the image origin but corrected about the centre left most of the shake in.
  * gaussian(): edge-padded smoothing used for camera paths, face paths and correction strength.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

ENVELOPE_HOP_S = 0.01   # 10 ms RMS frames for silence detection


def gaussian(v: np.ndarray, sigma_frames: float) -> np.ndarray:
    g = int(sigma_frames * 3)
    ker = np.exp(-0.5 * (np.arange(-g, g + 1) / sigma_frames) ** 2)
    ker /= ker.sum()
    return np.convolve(np.pad(v, g, mode="edge"), ker, mode="valid")


def centre_path(traj: np.ndarray, width: float, height: float) -> np.ndarray:
    """Cumulative (dx, dy, da) measured at the image origin -> the same path measured at the image centre."""
    inc = np.diff(traj, axis=0)
    c, s = np.cos(inc[:, 2]), np.sin(inc[:, 2])
    inc_c = np.stack([inc[:, 0] + (c - 1) * width / 2 - s * height / 2,
                      inc[:, 1] + s * width / 2 + (c - 1) * height / 2, inc[:, 2]], 1)
    return np.vstack([np.zeros(3), np.cumsum(inc_c, axis=0)])


def read_wav_mono(path: Path | str) -> tuple[np.ndarray, int]:
    """16-bit PCM WAV -> float32 mono in [-1, 1], sample rate."""
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit(f"{path}: expected 16-bit PCM WAV.")
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr


def envelope_db(path: Path | str) -> np.ndarray:
    """10 ms RMS level in dB over a mono 16-bit WAV (the cleaned edit track)."""
    x, sr = read_wav_mono(path)
    hop = int(sr * ENVELOPE_HOP_S)
    n = len(x) // hop
    return 10 * np.log10((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-10)
