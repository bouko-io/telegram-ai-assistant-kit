"""Voice notes -> text. Pluggable: anything with .transcribe(audio: bytes) -> str works.

Default: off. Set WHISPER_MODEL (for example "small") and `pip install faster-whisper`
to transcribe locally. See docs/recipes/voice-notes.md.

faster-whisper facts (README read 2026-11-27, https://github.com/SYSTRAN/faster-whisper):
- WhisperModel(size, device="cpu", compute_type="int8") runs on CPU.
- transcribe() returns (segments, info); segments is a GENERATOR, nothing runs until you iterate.
- info.language / info.language_probability report the detected language.
- Audio is decoded by PyAV (bundles FFmpeg libraries); no system ffmpeg needed.
- The README does not list supported formats. Telegram voice notes are usually OGG/Opus:
  test one of your own notes before relying on it (untested here).
"""

from __future__ import annotations

import os
import tempfile


class WhisperTranscriber:
    def __init__(self, model_size: str, language: str | None = None):
        from faster_whisper import WhisperModel  # optional dependency, imported only when used

        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.language = language  # None = auto-detect

    def transcribe(self, audio: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            segments, _info = self.model.transcribe(path, beam_size=5, language=self.language)
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            os.unlink(path)


def make_transcriber(model_size: str, language: str | None = None):
    if not model_size:
        return None
    return WhisperTranscriber(model_size, language)
