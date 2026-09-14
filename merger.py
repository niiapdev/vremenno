import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from config import WORK_DIR

logger = logging.getLogger(__name__)


async def merge_video_subtitles(video_path: Path, srt_path: Path) -> Path:
    loop = asyncio.get_event_loop()

    def _merge():
        output_path = WORK_DIR / f"{video_path.stem}_subtitled.mp4"

        tmp_dir = Path(tempfile.gettempdir())
        tmp_srt = tmp_dir / f"{video_path.stem}_filtersub.srt"
        shutil.copy2(str(srt_path), str(tmp_srt))

        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vf', f"subtitles='{tmp_srt.name}':force_style='FontSize=24,PrimaryColour=&H00FFFFFF'",
                '-c:a', 'copy',
                '-y',
                str(output_path)
            ]

            logger.info(f"Merging: {video_path.name} + {srt_path.name}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(tmp_dir),
                timeout=600
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")
        finally:
            tmp_srt.unlink(missing_ok=True)

        return output_path

    output_path = await loop.run_in_executor(None, _merge)

    if not output_path.exists():
        raise FileNotFoundError(f"Merged video not found: {output_path}")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Merged video: {output_path.name} ({size_mb:.1f}MB)")
    return output_path


def cleanup_files(*paths: Path) -> None:
    for path in paths:
        if path and path.exists():
            try:
                path.unlink()
                logger.info(f"Deleted: {path.name}")
            except Exception as e:
                logger.warning(f"Failed to delete {path.name}: {e}")