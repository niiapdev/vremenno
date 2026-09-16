import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR
from downloader import download_video
from translator import transcribe_video
from merger import merge_video_subtitles, cleanup_files

logger = logging.getLogger(__name__)


@dataclass
class Job:
    url: str
    user_id: int
    translate_to_ru: bool = False
    status: str = 'queued'
    result: Optional[Path] = None
    error: Optional[str] = None


class VideoPipeline:
    """Одна задача в моменте; очередь последовательная. Результат — в OUTPUT_DIR."""

    def __init__(self, max_concurrent: int = 1):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self.active: set = set()
        self._worker: Optional[asyncio.Task] = None

    def is_busy(self, user_id: int) -> bool:
        return user_id in self.active

    def submit(self, url: str, user_id: int, translate_to_ru: bool = False) -> Job:
        job = Job(url=url, user_id=user_id, translate_to_ru=translate_to_ru)
        self.queue.put_nowait(job)
        logger.info(f"[user={user_id}] Queued: {url}")
        return job

    def start(self):
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run())
            logger.info("Pipeline worker started")

    async def _run(self):
        while True:
            job = await self.queue.get()
            self.active.add(job.user_id)

            video_path = None
            srt_en_path = None
            srt_final_path = None
            merged_path = None

            try:
                job.status = 'downloading'
                video_path, _ = await download_video(job.url)

                job.status = 'transcribing'
                srt_en_path = await transcribe_video(video_path)
                srt_final_path = srt_en_path

                if job.translate_to_ru:
                    from deep_translator import GoogleTranslator
                    job.status = 'translating'
                    srt_final_path = await _translate_srt_to_ru(srt_en_path, job.user_id)

                job.status = 'merging'
                merged_path = await merge_video_subtitles(video_path, srt_final_path)

                final_path = OUTPUT_DIR / merged_path.name
                shutil.move(str(merged_path), str(final_path))

                job.status = 'done'
                job.result = final_path
                logger.info(f"[user={job.user_id}] Done: {final_path}")

            except Exception as e:
                job.status = 'failed'
                job.error = str(e)[:500]
                logger.error(f"[user={job.user_id}] Pipeline failed: {e}", exc_info=True)

            finally:
                self.active.discard(job.user_id)
                cleanup_files(video_path, srt_en_path, srt_final_path, merged_path)
                self.queue.task_done()

    @staticmethod
    async def _translate_srt_to_ru(srt_path: Path, user_id: int) -> Path:
        from deep_translator import GoogleTranslator

        def _translate():
            translator = GoogleTranslator(source='en', target='ru')

            def _parse_srt(content: str) -> list:
                texts = []
                for block in content.strip().split('\n\n'):
                    lines = block.split('\n')
                    if len(lines) >= 2:
                        texts.append(lines[-1])
                return texts

            def _rebuild_srt(content: str, translated: list) -> str:
                blocks = content.strip().split('\n\n')
                out = []
                for i, block in enumerate(blocks):
                    lines = block.split('\n')
                    if i < len(translated):
                        lines[-1] = translated[i]
                    out.append('\n'.join(lines))
                return '\n\n'.join(out)

            content = srt_path.read_text(encoding='utf-8')
            texts = _parse_srt(content)
            logger.info(f"[user={user_id}] Translating {len(texts)} segments EN->RU...")

            translated_texts = []
            for text in texts:
                try:
                    translated_texts.append(translator.translate(text))
                except Exception as e:
                    logger.warning(f"Translation failed for '{text[:40]}...': {e}")
                    translated_texts.append(text)

            ru_path = srt_path.parent / f"{srt_path.stem.replace('_en', '')}_ru.srt"
            ru_path.write_text(_rebuild_srt(content, translated_texts), encoding='utf-8')
            logger.info(f"[user={user_id}] RU SRT created: {ru_path.name}")
            return ru_path

        return await asyncio.to_thread(_translate)


pipeline = VideoPipeline()
