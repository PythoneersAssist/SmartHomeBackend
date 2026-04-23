from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from api.auth.endpoints import get_current_user
from database.database import get_db
from database.models import Notification, User
from api.notifications.ws_manager import connect_user_websocket, disconnect_user_websocket, utc_now_iso
from utils.security import ALGORITHM, SECRET_KEY


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize_notification(notification: Notification) -> dict[str, str | bool]:
    return {
        "id": str(notification.id),
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
    }


def _get_notification_for_user(db: Session, notification_id: UUID, user_id: UUID) -> Notification:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return notification


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


@router.get("/get")
def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    data = [_serialize_notification(notification) for notification in notifications]

    return JSONResponse(
        content={
            "message": f"Retrieved {len(data)} notifications",
            "notifications": data,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/unread_count")
def get_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )

    return JSONResponse(
        content={"unread_count": unread_count},
        status_code=status.HTTP_200_OK,
    )


@router.patch("/mark_read/{notification_id}")
def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    notification = _get_notification_for_user(db, notification_id, current_user.id)
    notification.is_read = True
    db.commit()

    return JSONResponse(
        content={"message": "Notification marked as read"},
        status_code=status.HTTP_200_OK,
    )


@router.patch("/mark_all_read")
def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    marked_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()

    return JSONResponse(
        content={"message": f"Marked {marked_count} notifications as read"},
        status_code=status.HTTP_200_OK,
    )


@router.delete("/delete/{notification_id}")
def delete_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    notification = _get_notification_for_user(db, notification_id, current_user.id)
    db.delete(notification)
    db.commit()

    return JSONResponse(
        content={"message": "Notification deleted successfully"},
        status_code=status.HTTP_200_OK,
    )


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