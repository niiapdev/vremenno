import asyncio
import logging
from pathlib import Path

import yt_dlp

from config import WORK_DIR, ALLOWED_FORMATS, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)


def _progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', 'N/A')
        logger.info(f"Downloading: {percent}")
    elif d['status'] == 'finished':
        logger.info("Download finished")


async def download_video(url: str) -> tuple:
    loop = asyncio.get_event_loop()

    def _download():
        output_template = str(WORK_DIR / '%(id)s.%(ext)s')

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'progress_hooks': [_progress_hook],
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'unknown')
            ext = info.get('ext', 'mp4')
            filepath = WORK_DIR / f"{video_id}.{ext}"

            if not filepath.exists():
                for f in WORK_DIR.glob(f"{video_id}.*"):
                    if f.suffix in ALLOWED_FORMATS:
                        filepath = f
                        break

            return filepath, info.get('title', 'video')

    filepath, title = await loop.run_in_executor(None, _download)

    if not filepath.exists():
        raise FileNotFoundError(f"Video not found after download: {filepath}")

    size_mb = filepath.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        filepath.unlink()
        raise ValueError(f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)")

    logger.info(f"Downloaded: {filepath.name} ({size_mb:.1f}MB)")
    return filepath, title