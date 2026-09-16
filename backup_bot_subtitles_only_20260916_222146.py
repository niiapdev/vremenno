import asyncio
import logging
import shutil

from pathlib import Path

from vkbottle.bot import Bot, Message

from config import VK_TOKEN, OUTPUT_DIR
from downloader import download_video
from translator import transcribe_video
from merger import cleanup_files

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
        "3. Создам английские субтитры (файл .srt)\n\n"
        "Видео и субтитры будут лежать в:\n"
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

    try:
        await message.answer("⏳ Скачиваю видео...")
        video_path, title = await download_video(url)

        await message.answer("⏳ Транскрибирую...")
        srt_en_path = await transcribe_video(video_path)

        srt_final_path = OUTPUT_DIR / f"{video_path.stem}.srt"
        shutil.copy2(str(srt_en_path), str(srt_final_path))

        video_final_path = OUTPUT_DIR / video_path.name
        shutil.move(str(video_path), str(video_final_path))

        await message.answer(
            f"✅ Готово! Субтитры и видео лежат в:\n\n"
            f"Субтитры (EN): {srt_final_path}\n"
            f"Видео: {video_final_path}"
        )

    except Exception as e:
        logger.error(f"Error processing video: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

    finally:
        processing_users.discard(user_id)
        cleanup_files(video_path, srt_en_path)


def main():
    if VK_TOKEN == 'YOUR_TOKEN_HERE':
        logger.error("Задай переменную окружения VK_TOKEN или вставь токен в config.py!")
        return

    logger.info("VK Bot started (subtitles only)")
    bot.run_forever()


if __name__ == '__main__':
    main()
