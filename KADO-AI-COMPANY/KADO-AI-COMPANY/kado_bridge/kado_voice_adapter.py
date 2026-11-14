"""PCM utilities and configured-provider fallback. No synthetic STT/TTS success."""
from __future__ import annotations
import math
import struct
from typing import Iterable, Protocol


def float32_to_pcm16(samples: Iterable[float]) -> bytes:
    values = []
    for sample in samples:
        if len(values) >= 16000 * 300:
            raise ValueError("Audio sample limit exceeded")
        sample = float(sample)
        if not math.isfinite(sample):
            sample = 0
        sample = min(1.0, max(-1.0, sample))
        values.append(round(sample * (32768 if sample < 0 else 32767)))
    return struct.pack("<" + "h" * len(values), *values)


class PCMFrameBuffer:
    """20 ms frames at 16 kHz mono int16; retains an independent byte copy."""
    sample_rate = 16000
    frame_bytes = 640

    def __init__(self, max_seconds: int = 5):
        self._buffer = bytearray()
        self.max_bytes = max_seconds * self.sample_rate * 2

    def push(self, pcm: bytes):
        if len(pcm) % 2:
            raise ValueError("PCM must contain complete int16 samples")
        if len(self._buffer) + len(pcm) > self.max_bytes:
            raise BufferError("Audio buffer overrun; producer must apply backpressure")
        self._buffer.extend(bytes(pcm))

    def pop(self) -> bytes | None:
        if len(self._buffer) < self.frame_bytes:
            return None
        frame = bytes(self._buffer[:self.frame_bytes])
        del self._buffer[:self.frame_bytes]
        return frame

    def clear_for_barge_in(self):
        """Discard queued assistant audio when existing transport detects speech."""
        discarded = len(self._buffer)
        self._buffer.clear()
        return discarded


class VoiceProvider(Protocol):
    name: str
    def transcribe(self, pcm: bytes, *, sample_rate: int) -> str: ...
    def synthesize(self, text: str, *, voice_id: str | None, sample_rate: int) -> bytes: ...


class KadoVoiceAdapter:
    def __init__(self, providers: list[VoiceProvider], *, voice_id: str | None = None):
        self.providers, self.voice_id = providers, voice_id
        self.failures = []

    def _call(self, operation: str, value):
        if not self.providers:
            raise RuntimeError("No existing KADO voice providers configured; STT/TTS unavailable")
        for provider in self.providers:
            try:
                if operation == "transcribe":
                    if not value or len(value) % 2 or len(value) > 16000 * 2 * 300:
                        raise ValueError("Expected nonempty PCM16 audio")
                    result = provider.transcribe(value, sample_rate=16000)
                    if not isinstance(result, str) or not result.strip():
                        raise RuntimeError("Provider returned no transcription")
                else:
                    result = provider.synthesize(value, voice_id=self.voice_id, sample_rate=16000)
                    if not isinstance(result, bytes) or not result or len(result) % 2:
                        raise RuntimeError("Provider returned invalid PCM16 audio")
                return result
            except Exception as exc:
                # Logs provider identity and failure class, never keys or raw API responses.
                self.failures.append({"provider": provider.name, "operation": operation, "error": type(exc).__name__})
        raise RuntimeError(f"All configured voice providers failed for {operation}")

    def transcribe(self, pcm: bytes):
        return self._call("transcribe", pcm)

    def synthesize(self, text: str):
        if not text.strip() or len(text) > 16000:
            raise ValueError("Bounded nonempty synthesis text required")
        return self._call("synthesize", text)
