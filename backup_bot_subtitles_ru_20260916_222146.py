import asyncio
import logging
import os
import shutil
from pathlib import Path

from deep_translator import GoogleTranslator

from vkbottle.bot import Bot, Message

from config import VK_TOKEN, OUTPUT_DIR
from downloader import download_video
from translator import transcribe_video
from merger import merge_video_subtitles, cleanup_files

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = Bot(token=VK_TOKEN)

processing_users = set()


def _format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _parse_srt(content: str) -> list:
    segments = []
    for block in content.strip().split('\n\n'):
        lines = block.split('\n')
        if len(lines) >= 2:
            segments.append(lines[-1])
    return segments


def _rebuild_srt(content: str, translated: list) -> str:
    blocks = content.strip().split('\n\n')
    out = []
    for i, block in enumerate(blocks):
        lines = block.split('\n')
        if i < len(translated):
            lines[-1] = translated[i]
        out.append('\n'.join(lines))
    return '\n\n'.join(out)


def _translate_srt_file(srt_path: Path) -> Path:
    content = srt_path.read_text(encoding='utf-8')
    texts = _parse_srt(content)
    logger.info(f"Translating {len(texts)} segments EN->RU...")

    translator = GoogleTranslator(source='en', target='ru')
    translated_texts = []
    for text in texts:
        try:
            translated_texts.append(translator.translate(text))
        except Exception as e:
            logger.warning(f"Translation failed for: {text[:50]}... {e}")
            translated_texts.append(text)

    ru_path = srt_path.parent / f"{srt_path.stem.replace('_en', '')}_ru.srt"
    ru_path.write_text(_rebuild_srt(content, translated_texts), encoding='utf-8')
    return ru_path


@bot.on.message(text="/start")
async def start(message: Message):
    await message.answer(
        "Привет! Отправь мне ссылку на видео, и я:\n"
        "1. Скачаю его\n"
        "2. Сделаю транскрипцию\n"
        "3. Переведу английские субтитры на русский\n"
        "4. Склею видео с русскими субтитрами\n\n"
        "Готовый файл будет лежать в:\n"
        f"{OUTPUT_DIR}"
    )


@bot.on.message()
async def handle_url(message: Message):
    url = message.text.strip()

    if not url.startswith(('http://', 'https://')):
        await message.answer("Отправь корректную ссылку на видео.")
        return

    user_id = message.peer_id
    if user_id in processing_users:
        await message.answer("Уже обрабатываю видео. Подожди.")
        return

    processing_users.add(user_id)

    video_path = None
    srt_en_path = None
    srt_ru_path = None
    merged_path = None

    try:
        await message.answer("⏳ Скачиваю видео...")
        video_path, title = await download_video(url)

        await message.answer("⏳ Транскрибирую...")
        srt_en_path = await transcribe_video(video_path)

        await message.answer("⏳ Переводлю EN->RU...")
        srt_ru_path = await asyncio.to_thread(_translate_srt_file, srt_en_path)

        await message.answer("⏳ Склеиваю видео с русскими субтитрами...")
        merged_path = await merge_video_subtitles(video_path, srt_ru_path)

        final_path = OUTPUT_DIR / merged_path.name
        shutil.move(str(merged_path), str(final_path))

        await message.answer(
            f"✅ Готово!\n\n"
            f"Файл: {final_path}"
        )

    except Exception as e:
        logger.error(f"Error processing video: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

    finally:
        processing_users.discard(user_id)
        cleanup_files(video_path, srt_en_path, srt_ru_path, merged_path)


def main():
    if VK_TOKEN == 'YOUR_TOKEN_HERE':
        logger.error("Задай переменную окружения VK_TOKEN или вставь токен в config.py!")
        return

    logger.info("VK Bot started (RU subtitles)")
    bot.run_forever()


if __name__ == '__main__':
    main()
