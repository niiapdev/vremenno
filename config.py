import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
WORK_DIR = BASE_DIR / 'video_for_whisper'
WORK_DIR.mkdir(exist_ok=True)

OUTPUT_DIR = BASE_DIR / 'video_subtitled'
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_FORMATS = ['.mp4', '.mkv', '.webm', '.avi']
MAX_FILE_SIZE_MB = 2000

WHISPER_MODEL = 'medium'
WHISPER_DEVICE = 'cpu'
WHISPER_COMPUTE_TYPE = 'int8'

DEFAULT_SOURCE_LANG = 'en'

VK_TOKEN = os.environ.get('VK_TOKEN', 'YOUR_TOKEN_HERE')