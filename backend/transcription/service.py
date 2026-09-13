from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from typing import Any, Callable, Optional

from transcription.chunker import TranscriptionChunker
from transcription.checkpoint import CheckpointManager
from transcription.formatter import TranscriptionFormatter
from core.exceptions import CustomException
from core.logging_config import get_logger

log = get_logger(__name__)


class TranscriptionService:
    def __init__(self) -> None:
        self._model_cache: dict[str, Any] = {}

    async def transcribe(self, request: Any, progress_callback: Callable[[float, str], None] | None = None) -> dict[str, Any]:
        raise NotImplementedError("Subclass must implement transcribe")


class WhisperXTranscriptionService(TranscriptionService):
    def __init__(self) -> None:
        self._model_cache: dict[str, Any] = {}

    async def transcribe(self, request: Any, progress_callback: Callable[[float, str], None] | None = None) -> dict[str, Any]:
        start = time.time()
        input_path = request.input_path
        if not os.path.exists(input_path):
            raise CustomException(message=f"Input file not found: {input_path}", code="FILE_NOT_FOUND", status_code=404)

        audio_path = input_path
        is_video = TranscriptionChunker.is_video_file(input_path)
        if is_video:
            if progress_callback:
                progress_callback(0.0, "Extracting audio from video...")
            audio_path = await TranscriptionChunker.ensure_wav_audio(input_path)

        try:
            import faster_whisper
        except ImportError:
            raise CustomException(
                message="faster-whisper is not installed. Install with: pip install faster-whisper",
                code="DEPENDENCY_MISSING",
                status_code=500,
            )

        model_key = f"{request.model_size}:cpu"
        if model_key not in self._model_cache:
            if progress_callback:
                progress_callback(0.0, "Loading model...")
            try:
                loop = asyncio.get_event_loop()
                model = await loop.run_in_executor(
                    None,
                    lambda: faster_whisper.WhisperModel(
                        request.model_size,
                        device="cpu",
                        compute_type="int8",
                    ),
                )
                self._model_cache[model_key] = model
            except Exception as exc:
                raise CustomException(message=f"Failed to load Whisper model: {exc}", code="MODEL_LOAD_FAILED", status_code=500) from exc
        else:
            model = self._model_cache[model_key]

        checkpoint_path = f"{input_path}.transcription_checkpoint.json"
        checkpoint = CheckpointManager.load(checkpoint_path)

        all_segments: list[dict] = []
        processed_chunks: list[dict] = []
        language = request.language or None

        if checkpoint:
            all_segments = checkpoint.get("segments", [])
            processed_chunks = checkpoint.get("processed_chunks", [])
            language = checkpoint.get("language", language)
            log.info(f"Resuming from checkpoint: {len(processed_chunks)} chunks already processed")

        duration = await asyncio.to_thread(TranscriptionChunker.estimate_duration, audio_path)
        chunks = TranscriptionChunker.estimate_chunks(duration, request.chunk_duration, request.chunk_overlap)

        log.info(f"Transcription input: audio_path={audio_path}, duration={duration:.2f}s, chunks={len(chunks)}, model={request.model_size}")

        diarize_fn = None
        if request.diarization:
            diarize_fn = await asyncio.to_thread(self._try_load_diarizer)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{chunk['start']:.3f}_{chunk['end']:.3f}"
            if any(c.get("id") == chunk_id for c in processed_chunks):
                log.debug(f"Skipping already processed chunk {chunk_id}")
                continue

            if progress_callback:
                progress_callback((idx / max(1, len(chunks))) * 90.0, f"Transcribing chunk {idx+1}/{len(chunks)}...")

            try:
                chunk_audio = await asyncio.to_thread(
                    TranscriptionChunker.extract_chunk_audio,
                    audio_path,
                    f"{audio_path}.chunk_{idx}.wav",
                    chunk["start"],
                    chunk["end"] - chunk["start"],
                )

                if not os.path.exists(chunk_audio) or os.path.getsize(chunk_audio) == 0:
                    log.warning(f"Chunk audio file missing or empty: {chunk_audio}")
                    continue

                segments_iter, info = await asyncio.to_thread(
                    model.transcribe,
                    chunk_audio,
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=1000, speech_pad_ms=400),
                    word_timestamps=True,
                )

                segments_list = list(segments_iter)

                if not segments_list:
                    log.warning(f"No segments found for chunk {idx} with VAD, retrying without VAD...")
                    segments_iter, info = await asyncio.to_thread(
                        model.transcribe,
                        chunk_audio,
                        language=language,
                        beam_size=3,
                        vad_filter=False,
                        word_timestamps=True,
                    )
                    segments_list = list(segments_iter)

                if not language and info.language:
                    language = info.language

                chunk_segments = []
                for seg in segments_list:
                    seg_data = {
                        "start": chunk["start"] + seg.start,
                        "end": chunk["start"] + seg.end,
                        "text": seg.text.strip(),
                        "confidence": round(getattr(seg, "avg_logprob", 0.0), 3),
                    }
                    if request.word_timestamps and seg.words:
                        seg_data["words"] = [
                            {
                                "start": chunk["start"] + w.start,
                                "end": chunk["start"] + w.end,
                                "word": w.word,
                                "probability": round(getattr(w, "probability", 1.0), 3),
                            }
                            for w in seg.words
                        ]
                    chunk_segments.append(seg_data)

                log.info(f"Chunk {idx} produced {len(chunk_segments)} segments")

                if not language and info.language:
                    language = info.language

                if diarize_fn and chunk_segments:
                    try:
                        await asyncio.to_thread(diarize_fn, chunk_audio, chunk_segments)
                    except Exception as exc:
                        log.warning(f"Diarization failed for chunk {idx}: {exc}")

                all_segments.extend(chunk_segments)
                processed_chunks.append({"id": chunk_id, "start": chunk["start"], "end": chunk["end"]})
                CheckpointManager.save(checkpoint_path, input_path, processed_chunks, all_segments, language or "en", request.model_size)

                try:
                    os.remove(chunk_audio)
                except OSError:
                    pass
                gc.collect()
            except Exception as exc:
                log.error(f"Chunk {idx} transcription failed: {exc}")
                raise CustomException(message=f"Transcription failed at chunk {idx+1}: {exc}", code="TRANSCRIPTION_CHUNK_FAILED", status_code=500) from exc

        if not all_segments and os.path.exists(audio_path):
            log.warning("All chunks returned 0 segments, attempting full-file transcription without chunking...")
            try:
                segments_iter, info = await asyncio.to_thread(
                    model.transcribe,
                    audio_path,
                    language=language,
                    beam_size=3,
                    vad_filter=False,
                    word_timestamps=True,
                )
                for seg in segments_iter:
                    all_segments.append({
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text.strip(),
                        "confidence": round(getattr(seg, "avg_logprob", 0.0), 3),
                        "words": [
                            {
                                "start": w.start,
                                "end": w.end,
                                "word": w.word,
                                "probability": round(getattr(w, "probability", 1.0), 3),
                            }
                            for w in seg.words
                        ] if request.word_timestamps and seg.words else None,
                    })
                if not language and info.language:
                    language = info.language
                log.info(f"Full-file fallback produced {len(all_segments)} segments")
            except Exception as exc:
                log.error(f"Full-file fallback transcription failed: {exc}")

        if progress_callback:
            progress_callback(90.0, "Writing outputs...")

        segments_out = [
            {
                "start": round(seg.get("start", 0), 3),
                "end": round(seg.get("end", 0), 3),
                "text": seg.get("text", "").strip(),
                "confidence": seg.get("confidence", 1.0),
                "speaker": seg.get("speaker"),
                "words": seg.get("words"),
            }
            for seg in all_segments
        ]

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = request.output_dir or os.path.dirname(input_path)
        metadata = {
            "input_path": input_path,
            "language": language or "en",
            "model_size": request.model_size,
            "duration_seconds": round(duration, 3),
        }
        outputs = TranscriptionFormatter.write_outputs(segments_out, output_dir, base_name, request.output_format, metadata)

        CheckpointManager.cleanup(checkpoint_path)

        processing_time = time.time() - start
        if progress_callback:
            progress_callback(100.0, "Completed")

        log.info(f"Transcription completed: {input_path} -> {len(segments_out)} segments in {processing_time:.2f}s")
        return {
            "input_path": input_path,
            "language": language or "en",
            "duration_seconds": round(duration, 3),
            "segments": segments_out,
            "processing_time_seconds": round(processing_time, 3),
            "model_used": request.model_size,
            "outputs": outputs,
            "warnings": [],
            "checkpoint_path": checkpoint_path,
        }

    def _try_load_diarizer(self) -> Callable | None:
        try:
            import whisperx
            from whisperx.diarize import DiarizationPipeline
            hf_token = os.getenv("HF_TOKEN", "")
            if not hf_token:
                log.warning("HF_TOKEN not set; diarization disabled")
                return None
            diarize_model = DiarizationPipeline(use_auth_token=hf_token, device="cpu")
            return lambda audio_path, segments: self._apply_diarization(diarize_model, audio_path, segments)
        except Exception as exc:
            log.warning(f"Could not load diarization model: {exc}")
            return None

    @staticmethod
    def _apply_diarization(diarize_model: Any, audio_path: str, segments: list[dict]) -> None:
        import numpy as np
        import librosa
        audio, _ = librosa.load(audio_path, sr=16000)
        diarize_segments = diarize_model(audio, min_speakers=2, max_speakers=5)
        if not diarize_segments:
            return
        speaker_map = {}
        speaker_counter = 1
        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            assigned = f"Speaker {speaker_counter}"
            for ds in diarize_segments:
                if ds.get("start", 0) <= seg_start < ds.get("end", 0):
                    assigned = ds.get("speaker", assigned)
                    break
            if assigned not in speaker_map:
                speaker_map[assigned] = f"Speaker {speaker_counter}"
                speaker_counter += 1
            seg["speaker"] = speaker_map[assigned]
