import asyncio
import logging
from pathlib import Path

from faster_whisper import WhisperModel

from config import WORK_DIR, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_whisper() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        _whisper_model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _whisper_model


def _format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _generate_srt(segments, output_path: Path) -> Path:
    srt_lines = []
    for i, segment in enumerate(segments, 1):
        start = _format_timestamp(segment.start)
        end = _format_timestamp(segment.end)
        text = segment.text.strip()
        srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")

    srt_content = "\n".join(srt_lines)
    output_path.write_text(srt_content, encoding='utf-8')
    return output_path


async def transcribe_video(video_path: Path, source_lang: str = None) -> Path:
    if source_lang is None:
        source_lang = 'en'

    loop = asyncio.get_event_loop()

    def _transcribe():
        model = _get_whisper()
        logger.info(f"Transcribing: {video_path.name}")

        segments_raw, info = model.transcribe(
            str(video_path),
            language=source_lang,
            task='transcribe',
            beam_size=5,
            vad_filter=True,
        )

        segments = list(segments_raw)
        logger.info(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")
        logger.info(f"Segments: {len(segments)}")
        return segments

    segments = await loop.run_in_executor(None, _transcribe)

    srt_path = WORK_DIR / f"{video_path.stem}_en.srt"
    _generate_srt(segments, srt_path)

    logger.info(f"SRT created: {srt_path}")
    return srt_path