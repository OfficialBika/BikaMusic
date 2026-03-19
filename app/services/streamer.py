from ntgcalls import AudioQuality, MediumQualityAudio
from pytgcalls.types.input_stream import AudioPiped
from app.core.tgcalls_client import call_py

async def start_stream(chat_id: int, stream_url: str):
    await call_py.play(
        chat_id,
        AudioPiped(
            stream_url,
            audio_parameters=MediumQualityAudio(),
        ),
    )
