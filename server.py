#!/usr/bin/env python3
"""
server.py — Wyoming TTS server wrapping Supertonic 3.
Exposes a TCP service that Home Assistant can discover and use.

Usage:
    python server.py --onnx-dir /path/to/assets/onnx \
                     --voice-dir /path/to/assets/voice_styles \
                     --port 10200
"""

import argparse
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer
from wyoming.tts import Synthesize

from tts_engine import AVAILABLE_LANGS, SupertonicTTS, Style, load_voice_style
from text_normalize import normalize

_LOGGER = logging.getLogger(__name__)

VOICES = {
    "M1": "Male 1",  "M2": "Male 2",  "M3": "Male 3",  "M4": "Male 4",  "M5": "Male 5",
    "F1": "Female 1","F2": "Female 2","F3": "Female 3","F4": "Female 4","F5": "Female 5",
}

DEFAULT_VOICE = "M1"
DEFAULT_LANG  = "en"
CHUNK_BYTES   = 4096   # ~93 ms at 22050 Hz 16-bit mono


class SupertonicHandler:
    """Stateless per-connection handler."""

    def __init__(self, tts: SupertonicTTS, voice_dir: Path,
                 default_voice: str, default_lang: str,
                 total_step: int, speed: float):
        self.tts           = tts
        self.voice_dir     = voice_dir
        self.default_voice = default_voice
        self.default_lang  = default_lang
        self.total_step    = total_step
        self.speed         = speed
        self._style_cache: dict[str, Style] = {}

    def _get_style(self, voice_id: str) -> Style:
        if voice_id not in self._style_cache:
            path = self.voice_dir / f"{voice_id}.json"
            if not path.exists():
                _LOGGER.warning("Voice %s not found, falling back to %s", voice_id, self.default_voice)
                path = self.voice_dir / f"{self.default_voice}.json"
            self._style_cache[voice_id] = load_voice_style([str(path)])
        return self._style_cache[voice_id]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        _LOGGER.debug("New connection from %s", addr)

        try:
            while True:
                # Read Wyoming framing: <length:4LE><json_line>\n
                header = await reader.readexactly(4)
                length = int.from_bytes(header, "little")
                data   = await reader.readexactly(length)
                line   = data.decode("utf-8")

                event = Event.from_json(line)

                if event.type == "describe":
                    await self._send_info(writer)

                elif Synthesize.is_type(event.type):
                    synth = Synthesize.from_event(event)
                    await self._synthesize(synth, writer)

        except asyncio.IncompleteReadError:
            pass
        except Exception as exc:
            _LOGGER.exception("Handler error: %s", exc)
        finally:
            writer.close()
            _LOGGER.debug("Connection closed: %s", addr)

    async def _send_info(self, writer: asyncio.StreamWriter):
        voices = [
            TtsVoice(
                name=vid,
                description=desc,
                attribution=Attribution(
                    name="Supertone Inc.",
                    url="https://github.com/supertone-inc/supertonic"
                ),
                installed=True,
                languages=AVAILABLE_LANGS,
            )
            for vid, desc in VOICES.items()
        ]

        info = Info(
            tts=[TtsProgram(
                name="supertonic",
                description="Supertonic 3 — On-device Neural TTS (31 languages)",
                attribution=Attribution(
                    name="Supertone Inc.",
                    url="https://github.com/supertone-inc/supertonic"
                ),
                installed=True,
                voices=voices,
            )]
        )
        await self._write_event(writer, info.event())

    async def _synthesize(self, synth: Synthesize, writer: asyncio.StreamWriter):
        text = normalize(synth.text)
        lang = (synth.voice.language or DEFAULT_LANG) if synth.voice else DEFAULT_LANG
        # Map BCP-47 like "en-US" → "en"
        lang = lang.split("-")[0].lower()
        if lang not in AVAILABLE_LANGS:
            lang = DEFAULT_LANG

        voice_name = (synth.voice.name or self.default_voice) if synth.voice else self.default_voice
        if voice_name not in VOICES:
            voice_name = self.default_voice

        _LOGGER.info("Synthesize | voice=%s lang=%s text=%r", voice_name, lang, text[:80])

        style = self._get_style(voice_name)
        sr    = self.tts.sample_rate

        # Run inference (blocking — offload to thread pool)
        loop = asyncio.get_event_loop()
        wav = await loop.run_in_executor(
            None,
            lambda: self.tts.synthesize(
                text, lang, style,
                total_step=self.total_step,
                speed=self.speed,
            )
        )

        pcm = SupertonicTTS.to_int16(wav)

        # Stream back
        await self._write_event(writer, AudioStart(
            rate=sr, width=2, channels=1
        ).event())

        for i in range(0, len(pcm), CHUNK_BYTES):
            chunk = pcm[i:i + CHUNK_BYTES]
            await self._write_event(writer, AudioChunk(
                rate=sr, width=2, channels=1, audio=chunk
            ).event())

        await self._write_event(writer, AudioStop().event())
        _LOGGER.info("Done | %.2f s audio", len(wav) / sr)

    @staticmethod
    async def _write_event(writer: asyncio.StreamWriter, event: Event):
        line = event.to_json() + "\n"
        data = line.encode("utf-8")
        writer.write(len(data).to_bytes(4, "little") + data)
        await writer.drain()


# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="Wyoming Supertonic TTS server")
    parser.add_argument("--onnx-dir",     required=True, help="Path to ONNX model directory")
    parser.add_argument("--voice-dir",    required=True, help="Path to voice_styles directory")
    parser.add_argument("--host",         default="0.0.0.0")
    parser.add_argument("--port",         type=int, default=10200)
    parser.add_argument("--voice",        default=DEFAULT_VOICE, choices=list(VOICES))
    parser.add_argument("--lang",         default=DEFAULT_LANG)
    parser.add_argument("--steps",        type=int, default=8, help="Denoising steps (quality)")
    parser.add_argument("--speed",        type=float, default=1.05)
    parser.add_argument("--log-level",    default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(message)s")

    _LOGGER.info("Loading Supertonic 3 models from %s …", args.onnx_dir)
    tts = SupertonicTTS(args.onnx_dir)
    _LOGGER.info("Models loaded. Sample rate: %d Hz", tts.sample_rate)

    handler = SupertonicHandler(
        tts=tts,
        voice_dir=Path(args.voice_dir),
        default_voice=args.voice,
        default_lang=args.lang,
        total_step=args.steps,
        speed=args.speed,
    )

    server = await asyncio.start_server(handler.handle, args.host, args.port)
    _LOGGER.info("Wyoming Supertonic ready on %s:%d", args.host, args.port)
    _LOGGER.info("Voices: %s", ", ".join(VOICES))

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
