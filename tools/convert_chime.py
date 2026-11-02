"""Convert the pick chime MP3 into the WAV bundled with the app.

Usage (from the project root):

    python tools/convert_chime.py path/to/ding.mp3

Writes ``assets/chime.wav`` (16-bit PCM at the source's sample rate and
channel count) which the exe ships and ``winsound`` plays when a student
is picked. Requires ``pip install miniaudio`` (see requirements-dev.txt).
"""

from __future__ import annotations

import array
import sys
import wave
from pathlib import Path

import miniaudio

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "chime.wav"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    if not source.is_file():
        print(f"File not found: {source}")
        return 1

    decoded = miniaudio.decode_file(str(source))
    seconds = decoded.num_frames / decoded.sample_rate

    pcm = array.array("h", decoded.samples)
    if sys.byteorder == "big":
        pcm.byteswap()

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(DEST), "wb") as out:
        out.setnchannels(decoded.nchannels)
        out.setsampwidth(2)
        out.setframerate(decoded.sample_rate)
        out.writeframes(pcm.tobytes())

    size = DEST.stat().st_size
    print(f"Wrote {DEST.relative_to(ROOT)} ({size:,} bytes, {decoded.nchannels}ch "
          f"{decoded.sample_rate} Hz, {seconds:.2f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())