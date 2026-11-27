# Recipe: voice notes with local Whisper

Turn voice notes into text on your own machine with faster-whisper, an open-source Whisper
reimplementation. Audio never leaves the server.

Facts from the faster-whisper README (read 2026-11-27, https://github.com/SYSTRAN/faster-whisper):

- Install: `pip install faster-whisper`. Python 3.9 or newer.
- No system FFmpeg needed: audio is decoded with PyAV, which bundles FFmpeg libraries.
- CPU: `WhisperModel("small", device="cpu", compute_type="int8")`.
  GPU: `device="cuda", compute_type="float16"`; needs NVIDIA cuBLAS and cuDNN 9 for CUDA 12.
- Model names mentioned in the README include `small`, `large-v2`, `large-v3`, `distil-large-v3`, `turbo`.
  Models download from the Hugging Face Hub on first use.
- `transcribe()` returns `(segments, info)`. `segments` is a generator: nothing runs until you iterate.
  `info.language` and `info.language_probability` give the detected language. Pass `language="xx"` to force one.

Not covered by the README: which audio formats work. Telegram voice notes are usually OGG/Opus.
PyAV normally decodes it, but test with one of your own notes (step 3).

Telegram side (Bot API docs read 2026-11-27): `message.voice` has `file_id`, `duration`, optional
`file_size`. `getFile` gives a `file_path`; download from `https://api.telegram.org/file/bot<token>/<file_path>`.
Bots can download at most 20 MB. The starter already does all of this in `bot.py`.

## Steps

1. `starter/.venv/bin/pip install faster-whisper`
2. In `.env`: `WHISPER_MODEL=small`. To force a language, extend `make_transcriber` in `voice.py` with a
   `WHISPER_LANGUAGE` env var (it already takes a `language` argument).
3. Test outside the bot first, with a note you saved from Telegram:
   ```bash
   cd starter && .venv/bin/python -c "
   import time, voice
   t = voice.make_transcriber('small')
   s = time.time(); print(t.transcribe(open('sample.ogg','rb').read())); print(round(time.time()-s,1),'s')"
   ```
4. Restart the bot. Send a voice note. You get "Heard: ..." first, then the answer.
5. Dialects: if words come out wrong, try a larger model, then forcing the language closest to the dialect.
   You can also add a line to the system prompt: "Voice transcripts may contain errors; if a request is
   unclear or would trigger an action, ask before proposing it."

## Swapping the engine

Anything with `transcribe(audio: bytes) -> str` works. A hosted speech API is a class of a few lines;
read its docs first (size limits, formats, price, where audio is stored).

## Done when

- Notes in each of the owner's languages come back with the right words.
- You wrote the measured time per 10 s of audio in `docs/decisions.md`.
- `test_voice_note_is_transcribed_echoed_and_answered` still passes.
