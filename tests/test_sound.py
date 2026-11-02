"""Chime playback tests."""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import pytest

from participation_tracker import sound


def test_bundled_chime_is_valid_pcm():
    path = sound.chime_path()
    assert path is not None and path.is_file()
    with wave.open(str(path)) as handle:
        assert handle.getnchannels() in (1, 2)
        assert handle.getsampwidth() == 2
        assert handle.getframerate() in (22050, 44100, 48000)
        assert handle.getnframes() > 0


def test_play_chime_uses_winsound_async(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sound, "chime_path", lambda: tmp_path / "chime.wav")
    (tmp_path / "chime.wav").write_bytes(b"RIFF")

    import winsound

    monkeypatch.setattr(winsound, "PlaySound", lambda name, flags: calls.append((name, flags)))

    sound.play_chime()

    assert len(calls) == 1
    assert str(calls[0][0]).endswith("chime.wav")
    # Asynchronous file playback, and no system default sound when the file fails.
    assert calls[0][1] & winsound.SND_ASYNC
    assert calls[0][1] & winsound.SND_FILENAME
    assert calls[0][1] & winsound.SND_NODEFAULT


def test_play_chime_ignores_playback_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sound, "chime_path", lambda: tmp_path / "missing.wav")

    import winsound

    def boom(name, flags):
        raise RuntimeError("no audio device")

    monkeypatch.setattr(winsound, "PlaySound", boom)
    sound.play_chime()  # must not raise


def test_play_chime_is_silent_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    calls = []

    import winsound

    monkeypatch.setattr(winsound, "PlaySound", lambda name, flags: calls.append(name))
    sound.play_chime()
    assert calls == []