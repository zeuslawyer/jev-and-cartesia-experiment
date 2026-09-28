import asyncio
import json

TURNS = json.load(open("data/turns.json"))


async def replay_turn_events(turn):
    """Fake microphone: yields scripted Ink-2 turn events, waiting the real gap between each."""
    last_ms = 0
    for event in turn["events"]:
        await asyncio.sleep((event["t_ms"] - last_ms) / 1000)
        last_ms = event["t_ms"]
        yield event


# Real Ink-2 swap (Cartesia SDK), same events:
#   async with client.stt.auto_finalize.websocket(model="ink-2", encoding="pcm_s16le", sample_rate=16000) as ink2:
#       async for event in ink2:   # event.type, event.transcript
