import asyncio
import logging
import shutil

from pathlib import Path

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


@bot.on.message(text="/start")
async def start(message: Message):
    await message.answer(
        "Привет! Отправь мне ссылку на видео, и я:\n"
        "1. Скачаю его\n"
        "2. Сделаю транскрипцию\n"
        "3. Вставлю АНГЛИЙСКИЕ субтитры\n\n"
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
    merged_path = None

    try:
        await message.answer("⏳ Скачиваю видео...")
        video_path, title = await download_video(url)

        await message.answer("⏳ Транскрибирую...")
        srt_en_path = await transcribe_video(video_path)

        await message.answer("⏳ Склеиваю видео с субтитрами...")
        merged_path = await merge_video_subtitles(video_path, srt_en_path)

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
        cleanup_files(video_path, srt_en_path, merged_path)


def main():
    if VK_TOKEN == 'YOUR_TOKEN_HERE':
        logger.error("Задай переменную окружения VK_TOKEN или вставь токен в config.py!")
        return

    logger.info("VK Bot started")
    bot.run_forever()


if __name__ == '__main__':
    main()
