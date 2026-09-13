from __future__ import annotations

import asyncio
import io
import time
import logging
import numpy as np
from scipy import signal
from scipy.io import wavfile
import noisereduce as nr

from audio.enhancement.schema import AudioEnhanceRequest, AudioEnhanceResponse, AudioPreviewRequest
from core.logging_config import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16000

ZONE_PRESETS = {
    "mild": {
        "label": "Mild (Room Hum)",
        "prop_decrease": 0.3,
        "freq_mask_smooth_hz": 20.0,
        "time_constant_s": 1.0,
        "suppression_db": 6,
        "reverb_decay": 0.85,
    },
    "balanced": {
        "label": "Balanced Studio",
        "prop_decrease": 0.6,
        "freq_mask_smooth_hz": 15.0,
        "time_constant_s": 0.5,
        "suppression_db": 12,
        "reverb_decay": 0.65,
    },
    "max": {
        "label": "Max Vocal Isolation",
        "prop_decrease": 0.9,
        "freq_mask_smooth_hz": 10.0,
        "time_constant_s": 0.3,
        "suppression_db": 24,
        "reverb_decay": 0.40,
    },
}


def _map_strength_to_preset(strength: int) -> dict:
    if strength <= 30:
        return ZONE_PRESETS["mild"]
    elif strength <= 70:
        return ZONE_PRESETS["balanced"]
    else:
        return ZONE_PRESETS["max"]


def _apply_hum_filter(audio: np.ndarray, sr: int) -> np.ndarray:
    sos = signal.butter(4, [49.0, 51.0], btype="bandstop", fs=sr, output="sos")
    filtered = signal.sosfiltfilt(sos, audio)
    for harmonic in [2, 3, 4, 5, 6]:
        f0 = harmonic * 50.0
        bw = 4.0
        sos_h = signal.butter(2, [f0 - bw, f0 + bw], btype="bandstop", fs=sr, output="sos")
        filtered = signal.sosfiltfilt(sos_h, filtered)
    return filtered


def _apply_de_reverb(audio: np.ndarray, sr: int, decay: float) -> np.ndarray:
    window_size = int(0.02 * sr)
    if window_size % 2 == 0:
        window_size += 1
    hop = window_size // 2

    padded = np.pad(audio, (window_size // 2, window_size // 2), mode="reflect")
    output = np.zeros_like(audio)

    for i in range(0, len(audio), hop):
        frame = padded[i : i + window_size]
        spectrum = np.fft.rfft(frame)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)

        noise_floor = np.percentile(magnitude, 15)
        clean_mag = np.maximum(magnitude - noise_floor * (1.0 - decay), 0)
        spectral_shape = np.maximum(clean_mag, magnitude * decay)
        clean_spectrum = spectral_shape * np.exp(1j * phase)

        clean_frame = np.fft.irfft(clean_spectrum, n=window_size)
        win = np.hanning(window_size)
        clean_frame = clean_frame * win

        end = min(i + hop, len(audio))
        output[i:end] += clean_frame[: end - i]

    return output


def _apply_vocal_eq(audio: np.ndarray, sr: int) -> np.ndarray:
    sos_highpass = signal.butter(2, 80, btype="highpass", fs=sr, output="sos")
    audio = signal.sosfiltfilt(sos_highpass, audio)

    sos_presence = signal.butter(2, [2500, 5000], btype="bandpass", fs=sr, output="sos")
    presence = signal.sosfiltfilt(sos_presence, audio) * 0.25
    audio = audio + presence

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95

    return audio


def _apply_ai_denoise(audio: np.ndarray, sr: int, preset: dict) -> np.ndarray:
    try:
        reduced = nr.reduce_noise(
            y=audio,
            sr=sr,
            prop_decrease=preset["prop_decrease"],
            freq_mask_smooth_hz=max(31.0, preset["freq_mask_smooth_hz"]),
            time_constant_s=preset["time_constant_s"],
        )
        return reduced
    except Exception as e:
        log.warning(f"AI denoise fallback: {e}")
        sos = signal.butter(2, 3000, btype="lowpass", fs=sr, output="sos")
        return signal.sosfiltfilt(sos, audio)


def process_audio_pipeline(audio: np.ndarray, sr: int, config: dict) -> tuple[np.ndarray, dict]:
    applied: dict = {}

    if config.get("hum_filter", True):
        audio = _apply_hum_filter(audio, sr)
        applied["hum_filter"] = "active"

    if config.get("de_reverb", True):
        preset = _map_strength_to_preset(config.get("noise_suppression_strength", 90))
        audio = _apply_de_reverb(audio, sr, preset["reverb_decay"])
        applied["de_reverb"] = "active"

    if config.get("ai_denoise", True):
        preset = _map_strength_to_preset(config.get("noise_suppression_strength", 90))
        audio = _apply_ai_denoise(audio, sr, preset)
        applied["ai_denoise"] = {
            "strength": config.get("noise_suppression_strength", 90),
            "preset": preset["label"],
            "suppression_db": preset["suppression_db"],
        }

    if config.get("vocal_clarity_eq", True):
        audio = _apply_vocal_eq(audio, sr)
        applied["vocal_clarity_eq"] = "active"

    return audio, applied


def audio_bytes_to_np(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    sr, data = wavfile.read(io.BytesIO(audio_bytes))
    if data.dtype == np.int16:
        audio = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        audio = data.astype(np.float32) / 2147483648.0
    else:
        audio = data.astype(np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    return audio, sr


def np_to_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95
    pcm = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    wavfile.write(buf, sr, pcm)
    return buf.getvalue()


def generate_test_tone(frequency_hz: float, duration_seconds: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(sr * duration_seconds), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * frequency_hz * t)
    noise = 0.05 * np.random.randn(len(t))
    hum = 0.08 * np.sin(2 * np.pi * 60 * t) + 0.06 * np.sin(2 * np.pi * 120 * t)
    audio = tone + noise + hum
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.8
    return audio.astype(np.float32)


class AudioService:
    async def process_audio(self, request: AudioEnhanceRequest, audio_bytes: bytes) -> AudioEnhanceResponse:
        start = time.time()
        try:
            audio, sr = await asyncio.to_thread(audio_bytes_to_np, audio_bytes)
            processed, applied = await asyncio.to_thread(process_audio_pipeline, audio, sr, request.config)
            output_bytes = await asyncio.to_thread(np_to_wav_bytes, processed, sr)
            processed_url = self._upload_processed(output_bytes, request.audio_url)
            elapsed = time.time() - start
            return AudioEnhanceResponse(
                success=True,
                processed_url=processed_url,
                processing_time_seconds=round(elapsed, 2),
                sample_rate=sr,
                duration_seconds=round(len(processed) / sr, 2),
                applied_settings=applied,
            )
        except Exception as e:
            log.error(f"Audio processing failed: {e}")
            return AudioEnhanceResponse(
                success=False,
                processing_time_seconds=round(time.time() - start, 2),
                sample_rate=SAMPLE_RATE,
                duration_seconds=0.0,
                applied_settings={},
                error=str(e),
            )

    def _upload_processed(self, audio_bytes: bytes, original_url: str) -> str:
        return f"processed://{id(audio_bytes)}"

    async def generate_preview(self, request: AudioPreviewRequest) -> AudioEnhanceResponse:
        start = time.time()
        try:
            audio = await asyncio.to_thread(
                generate_test_tone, request.frequency_hz, request.duration_seconds, SAMPLE_RATE
            )
            processed, applied = await asyncio.to_thread(
                process_audio_pipeline, audio, SAMPLE_RATE, request.config
            )
            output_bytes = await asyncio.to_thread(np_to_wav_bytes, processed, SAMPLE_RATE)
            preview_url = f"preview://{id(output_bytes)}"
            elapsed = time.time() - start
            return AudioEnhanceResponse(
                success=True,
                processed_url=preview_url,
                processing_time_seconds=round(elapsed, 2),
                sample_rate=SAMPLE_RATE,
                duration_seconds=request.duration_seconds,
                applied_settings=applied,
            )
        except Exception as e:
            log.error(f"Preview generation failed: {e}")
            return AudioEnhanceResponse(
                success=False,
                processing_time_seconds=round(time.time() - start, 2),
                sample_rate=SAMPLE_RATE,
                duration_seconds=0.0,
                applied_settings={},
                error=str(e),
            )
