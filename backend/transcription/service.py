from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from typing import Any, Callable, Optional

from transcription.word_timing import clean_word_timings
from transcription.chunker import TranscriptionChunker
from transcription.checkpoint import CheckpointManager
from transcription.formatter import TranscriptionFormatter
from transcription.schema import (
    BatchTranscriptionRequest,
    BatchTranscriptionResult,
    TranscriptionRequest,
    TranscriptionResult,
)
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from transcription.groq_whisper import GroqWhisperTranscriber

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

        duration = await asyncio.to_thread(TranscriptionChunker.estimate_duration, audio_path)
        diarize_fn = await asyncio.to_thread(self._try_load_diarizer) if request.diarization else None
        # Speaker turns are computed over the whole file once, alongside the
        # transcription, so labels agree from the first minute to the last.
        turns_task = asyncio.create_task(asyncio.to_thread(diarize_fn, audio_path)) if diarize_fn else None

        hosted = await self._transcribe_hosted(request, audio_path, duration, progress_callback)
        if hosted is not None:
            segments, language = hosted
            await self._label_speakers(segments, turns_task)
            return self._finish(request, input_path, segments, language, duration, start, progress_callback, model_used=GroqWhisperTranscriber().model)

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
                        cpu_threads=self._cpu_threads(),
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

        chunks = TranscriptionChunker.estimate_chunks(duration, request.chunk_duration, request.chunk_overlap)

        log.info(f"Transcription input: audio_path={audio_path}, duration={duration:.2f}s, chunks={len(chunks)}, model={request.model_size}")

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

                segments_list, info = await asyncio.to_thread(
                    self._transcribe_sync,
                    model,
                    chunk_audio,
                    language=language,
                    initial_prompt=request.prompt or None,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=1000, speech_pad_ms=400),
                    word_timestamps=True,
                )

                if not segments_list:
                    log.warning(f"No segments found for chunk {idx} with VAD, retrying without VAD...")
                    segments_list, info = await asyncio.to_thread(
                        self._transcribe_sync,
                        model,
                        chunk_audio,
                        language=language,
                        initial_prompt=request.prompt or None,
                        beam_size=3,
                        vad_filter=False,
                        word_timestamps=True,
                    )

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

                all_segments.extend(chunk_segments)
                processed_chunks.append({"id": chunk_id, "start": chunk["start"], "end": chunk["end"]})
                CheckpointManager.save(checkpoint_path, input_path, processed_chunks, all_segments, language or "en", request.model_size)

                try:
                    os.remove(chunk_audio)
                except OSError:
                    pass
                gc.collect()
                await asyncio.sleep(0)
            except Exception as exc:
                log.error(f"Chunk {idx} transcription failed: {exc}")
                raise CustomException(message=f"Transcription failed at chunk {idx+1}: {exc}", code="TRANSCRIPTION_CHUNK_FAILED", status_code=500) from exc

        if not all_segments and os.path.exists(audio_path):
            log.warning("All chunks returned 0 segments, attempting full-file transcription without chunking...")
            try:
                segments_list, info = await asyncio.to_thread(
                    self._transcribe_sync,
                    model,
                    audio_path,
                    language=language,
                    initial_prompt=request.prompt or None,
                    beam_size=3,
                    vad_filter=False,
                    word_timestamps=True,
                )
                for seg in segments_list:
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

        await self._label_speakers(all_segments, turns_task)
        return self._finish(request, input_path, all_segments, language, duration, start, progress_callback, model_used=request.model_size, checkpoint_path=checkpoint_path)

    async def _transcribe_hosted(
        self, request: Any, audio_path: str, duration: float, progress_callback: Callable[[float, str], None] | None,
    ) -> tuple[list[dict[str, Any]], str] | None:
        """Transcribe on Groq's hosted Whisper when configured; ``None`` to run locally."""
        provider = (getattr(get_settings(), "TRANSCRIPTION_PROVIDER", "auto") or "auto").strip().lower()
        if provider == "local" or not GroqWhisperTranscriber.available():
            return None
        if progress_callback:
            progress_callback(5.0, "Transcribing with hosted Whisper...")
        try:
            segments, language = await GroqWhisperTranscriber().transcribe(
                audio_path, duration, request.language, prompt=request.prompt,
            )
        except Exception as exc:
            log.warning("Hosted transcription failed, falling back to local Whisper: %s", exc)
            return None
        if not segments:
            log.warning("Hosted transcription returned no speech, falling back to local Whisper")
            return None
        return segments, language

    async def _label_speakers(self, segments: list[dict], turns_task: asyncio.Task | None) -> None:
        if turns_task is None:
            return
        try:
            turns = await turns_task
        except Exception as exc:
            log.warning(f"Diarization failed: {exc}")
            return
        assign_speakers(segments, turns or [])

    def _finish(
        self,
        request: Any,
        input_path: str,
        all_segments: list[dict],
        language: str | None,
        duration: float,
        start: float,
        progress_callback: Callable[[float, str], None] | None,
        model_used: str,
        checkpoint_path: str | None = None,
    ) -> dict[str, Any]:
        if progress_callback:
            progress_callback(90.0, "Writing outputs...")

        segments_out = [
            {
                "start": round(seg.get("start", 0), 3),
                "end": round(seg.get("end", 0), 3),
                "text": seg.get("text", "").strip(),
                "confidence": seg.get("confidence", 1.0),
                "speaker": seg.get("speaker"),
                "words": clean_word_timings(seg["words"]) if seg.get("words") else seg.get("words"),
            }
            for seg in all_segments
        ]

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = request.output_dir or os.path.dirname(input_path)
        metadata = {
            "input_path": input_path,
            "language": language or "en",
            "model_size": model_used,
            "duration_seconds": round(duration, 3),
        }
        outputs = TranscriptionFormatter.write_outputs(segments_out, output_dir, base_name, request.output_format, metadata)

        if checkpoint_path:
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
            "model_used": model_used,
            "outputs": outputs,
            "warnings": [],
            "checkpoint_path": checkpoint_path,
        }

    async def transcribe_request(self, request: TranscriptionRequest) -> TranscriptionResult:
        def _progress(percent: float, message: str) -> None:
            log.info(f"Transcription progress: {percent:.1f}% - {message}")

        return TranscriptionResult(**await self.transcribe(request, progress_callback=_progress))

    async def batch_transcribe(self, request: BatchTranscriptionRequest) -> BatchTranscriptionResult:
        """Transcribe every input, at most ``max_workers`` at a time. The first
        failure aborts the batch."""
        semaphore = asyncio.Semaphore(request.max_workers)

        async def _run(input_path: str) -> dict[str, Any]:
            single = TranscriptionRequest(
                input_path=input_path,
                model_size=request.model_size,
                language=request.language,
                chunk_duration=request.chunk_duration,
                chunk_overlap=request.chunk_overlap,
                word_timestamps=request.word_timestamps,
                diarization=request.diarization,
                output_format=request.output_format,
                output_dir=request.output_dir,
                device=request.device,
            )
            async with semaphore:
                return await self.transcribe(single)

        results = await asyncio.gather(*[_run(path) for path in request.input_paths])
        return BatchTranscriptionResult(
            total=len(request.input_paths),
            completed=len(results),
            failed=0,
            results=[TranscriptionResult(**r) for r in results],
            processing_time_seconds=0.0,
        )

    @staticmethod
    def _cpu_threads() -> int:
        """Leave at least one core free so the API event loop stays responsive.

        Defaults to (cores - 1); override with WHISPER_CPU_THREADS.
        """
        override = os.getenv("WHISPER_CPU_THREADS")
        if override:
            try:
                return max(1, int(override))
            except ValueError:
                log.warning(f"Invalid WHISPER_CPU_THREADS={override!r}, ignoring")
        return max(1, (os.cpu_count() or 2) - 1)

    @staticmethod
    def _transcribe_sync(model: Any, audio_path: str, **kwargs: Any) -> tuple[list, Any]:
        """Transcribe AND drain the segment generator inside the worker thread.

        faster-whisper returns a lazy generator: the decoding happens on iteration,
        not in transcribe(). Consuming it on the event loop thread blocks every
        other request for the length of the chunk.
        """
        segments_iter, info = model.transcribe(audio_path, **kwargs)
        return list(segments_iter), info

    def _try_load_diarizer(self) -> Callable[[str], list[dict]] | None:
        """A function returning speaker turns for an audio file, or None if unavailable."""
        try:
            from whisperx.diarize import DiarizationPipeline
            hf_token = (get_settings().HF_TOKEN or "").strip()
            if not hf_token:
                log.warning("HF_TOKEN not set; diarization disabled")
                return None
            diarize_model = DiarizationPipeline(use_auth_token=hf_token, device="cpu")
            return lambda audio_path: self._diarization_turns(diarize_model, audio_path)
        except Exception as exc:
            log.warning(f"Could not load diarization model: {exc}")
            return None

    @staticmethod
    def _diarization_turns(diarize_model: Any, audio_path: str) -> list[dict]:
        import librosa
        audio, _ = librosa.load(audio_path, sr=16000)
        # No min_speakers: forcing two split every solo talker into two people.
        turns = diarize_model(audio, max_speakers=6)
        if hasattr(turns, "to_dict"):
            turns = turns.to_dict("records")
        return [
            {"start": float(t.get("start", 0.0)), "end": float(t.get("end", 0.0)), "speaker": str(t.get("speaker"))}
            for t in (turns or [])
        ]


def assign_speakers(segments: list[dict], turns: list[dict]) -> None:
    """Label each segment with the speaker whose turns overlap it most.

    Labels are numbered in order of first appearance, so "Speaker 1" is
    whoever talks first and keeps that name for the whole video.
    """
    if not turns:
        return
    names: dict[str, str] = {}
    for seg in segments:
        seg_start, seg_end = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
        overlap: dict[str, float] = {}
        for turn in turns:
            shared = min(seg_end, turn["end"]) - max(seg_start, turn["start"])
            if shared > 0:
                overlap[turn["speaker"]] = overlap.get(turn["speaker"], 0.0) + shared
        if not overlap:
            continue
        raw = max(overlap, key=overlap.get)
        names.setdefault(raw, f"Speaker {len(names) + 1}")
        seg["speaker"] = names[raw]
