import asyncio
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import WebSocket


logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class NotificationWebSocketManager:
    def __init__(self) -> None:
        self._connections_by_user: dict[str, set[WebSocket]] = {}
        self._lock = Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        with self._lock:
            self._connections_by_user.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        with self._lock:
            user_connections = self._connections_by_user.get(user_id)
            if not user_connections:
                return
            user_connections.discard(websocket)
            if not user_connections:
                self._connections_by_user.pop(user_id, None)

    async def _send_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            recipients = list(self._connections_by_user.get(user_id, set()))

        disconnected: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(payload)
            except Exception as exc:
                logger.debug("Failed to send websocket notification: %s", exc)
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.disconnect(user_id, websocket)

    def notify_user(self, user_id: str, payload: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return

        coroutine = self._send_to_user(user_id, payload)

        try:
            running_loop = asyncio.get_running_loop()
            if running_loop == self._loop:
                running_loop.create_task(coroutine)
                return
        except RuntimeError:
            pass

        asyncio.run_coroutine_threadsafe(coroutine, self._loop)


manager = NotificationWebSocketManager()


async def connect_user_websocket(user_id: str, websocket: WebSocket) -> None:
    await manager.connect(user_id, websocket)


async def disconnect_user_websocket(user_id: str, websocket: WebSocket) -> None:
    await manager.disconnect(user_id, websocket)


def notify_user(user_id: str, payload: dict[str, Any]) -> None:
    manager.notify_user(user_id, payload)


def notify_device_status_changed(user_id: str, device_id: str, is_on: bool) -> None:
    notify_user(
        user_id,
        {
            "event": "deviceStatusChanged",
            "deviceId": device_id,
            "status": "on" if is_on else "off",
            "timestamp": utc_now_iso(),
        },
    )


def notify_automation_triggered(
    user_id: str,
    automation_id: str,
    automation_name: str,
    device_id: str,
    trigger_type: Any,
    trigger_value: Any,
    reason: str,
) -> None:
    notify_user(
        user_id,
        {
            "event": "automationTriggered",
            "automationId": automation_id,
            "automationName": automation_name,
            "deviceId": device_id,
            "triggerType": trigger_type,
            "triggerValue": trigger_value,
            "reason": reason,
            "timestamp": utc_now_iso(),
        },
    )


def notify_automation_changed(user_id: str, action: str, automation_id: str, automation_name: str) -> None:
    notify_user(
        user_id,
        {
            "event": "automationChanged",
            "action": action,
            "automationId": automation_id,
            "automationName": automation_name,
            "timestamp": utc_now_iso(),
        },
    )
