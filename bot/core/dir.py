import shutil
from pathlib import Path

from bot import logger


def ensure_dirs():
    if not shutil.which("deno") or not shutil.which("ffmpeg"):
        raise RuntimeError(
            "Deno and FFmpeg must be installed and available in system PATH."
        )

    for dir in ["cache", "downloads"]:
        Path(dir).mkdir(parents=True, exist_ok=True)

    logger.info("Required directories checked and updated.")
