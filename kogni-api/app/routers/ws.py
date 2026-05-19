"""
Kogni WebSocket Router
=======================
Subscribes to Redis pub/sub channel for a user and streams
live fatigue scores + recovery interventions to the dashboard.

Connect from the browser extension or dashboard:
    const ws = new WebSocket("ws://localhost:8000/api/v1/ws/live?token=<jwt>")
    ws.onmessage = (e) => {
        const { fatigue_score, status, shap_top3 } = JSON.parse(e.data)
    }
"""

import json
import asyncio
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.core.config import settings

router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_user_id_from_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None


@router.websocket("/live")
async def live_score(websocket: WebSocket, token: str = Query(...)):
    """
    Stream live fatigue scores to a connected client.
    Auth via JWT passed as query param (can't set headers in WebSocket).
    """
    user_id = await get_user_id_from_token(token)
    if user_id is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"kogni:live:{user_id}")

    # Send the latest cached score immediately on connect
    cached = await r.get(f"kogni:score:{user_id}")
    if cached:
        await websocket.send_text(cached)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_text(message["data"])
                except WebSocketDisconnect:
                    break
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await pubsub.unsubscribe(f"kogni:live:{user_id}")
        await r.aclose()
