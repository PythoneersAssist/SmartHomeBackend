from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from uuid import UUID

from api.notifications.ws_manager import connect_user_websocket, disconnect_user_websocket, utc_now_iso
from utils.security import ALGORITHM, SECRET_KEY


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _decode_user_id_from_token(token: str | None) -> str | None:
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_user_id = payload.get("id")
        if token_user_id is None:
            return None
        return str(UUID(token_user_id))
    except (ValueError, JWTError, TypeError):
        return None


def _extract_token(websocket: WebSocket) -> str | None:
    token_from_query = websocket.query_params.get("token")
    if token_from_query:
        return token_from_query

    auth_header = websocket.headers.get("authorization")
    if not auth_header:
        return None

    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None


@router.websocket("/ws")
async def notifications_websocket(websocket: WebSocket) -> None:
    token = _extract_token(websocket)
    user_id = _decode_user_id_from_token(token)

    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await connect_user_websocket(user_id, websocket)
    await websocket.send_json(
        {
            "event": "connected",
            "timestamp": utc_now_iso(),
        }
    )

    try:
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"event": "pong", "timestamp": utc_now_iso()})
    except WebSocketDisconnect:
        pass
    finally:
        await disconnect_user_websocket(user_id, websocket)