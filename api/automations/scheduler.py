import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta, timezone
from os import getenv
from typing import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.automations.logic import execute_automation_device_action
from api.notifications.ws_manager import notify_automation_triggered, notify_device_status_changed
from database.database import SessionLocal
from database.enums import AutomationTriggerType
from database.models import Automation, AutomationExecution, AutomationSchedulerState


logger = logging.getLogger(__name__)
UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc_iso(timestamp: datetime) -> str:
    normalized = timestamp.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def parse_utc_iso(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_time_trigger(value: str | None) -> dt_time | None:
    if not value:
        return None

    raw = value.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def _positive_float_from_env(name: str, default: float) -> float:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def is_scheduler_enabled() -> bool:
    return getenv("AUTOMATION_SCHEDULER_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


def _poll_seconds() -> float:
    return _positive_float_from_env("AUTOMATION_SCHEDULER_POLL_SECONDS", 5.0)


def _recovery_hours() -> float:
    return _positive_float_from_env("AUTOMATION_SCHEDULER_RECOVERY_HOURS", 24.0)


def _iter_due_slots(automation: Automation, window_start: datetime, window_end: datetime) -> Iterable[datetime]:
    trigger_time = parse_time_trigger(automation.trigger_value)
    if trigger_time is None:
        return []

    due_slots: list[datetime] = []
    current_day = window_start.date()
    last_day = window_end.date()

    while current_day <= last_day:
        candidate = datetime.combine(current_day, trigger_time, tzinfo=UTC)
        if automation.execution_day is not None and candidate.weekday() != automation.execution_day:
            current_day += timedelta(days=1)
            continue
        if window_start < candidate <= window_end:
            due_slots.append(candidate)
        current_day += timedelta(days=1)

    return due_slots


def _get_or_create_scheduler_state(db: Session, now: datetime) -> AutomationSchedulerState:
    state = db.query(AutomationSchedulerState).filter(AutomationSchedulerState.id == 1).first()
    if state:
        return state

    default_start = now - timedelta(hours=_recovery_hours())
    state = AutomationSchedulerState(id=1, last_checked_at=to_utc_iso(default_start))
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def _try_execute_due_automation(db: Session, automation: Automation, scheduled_for: datetime) -> bool:
    execution = AutomationExecution(
        automation_id=automation.id,
        scheduled_for=to_utc_iso(scheduled_for),
        executed_at=to_utc_iso(utc_now()),
        status="executed",
        error_message=None,
    )

    db.add(execution)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False

    try:
        if automation.device is None or automation.device.room is None or automation.device.room.house is None:
            execution.status = "failed"
            execution.error_message = "Automation target hierarchy is incomplete"
            db.commit()
            return False

        user_id = str(automation.device.room.house.user_id)
        device_id = str(automation.device.id)

        changed = execute_automation_device_action(automation.device)
        db.commit()

        notify_automation_triggered(
            user_id=user_id,
            automation_id=str(automation.id),
            automation_name=automation.name,
            device_id=device_id,
            trigger_type=automation.trigger_type.value if automation.trigger_type is not None else None,
            trigger_value=automation.trigger_value,
            reason="scheduledTime",
        )

        if changed:
            notify_device_status_changed(user_id, device_id, True)

        return True
    except Exception as exc:
        db.rollback()
        db.add(
            AutomationExecution(
                automation_id=automation.id,
                scheduled_for=to_utc_iso(scheduled_for),
                executed_at=to_utc_iso(utc_now()),
                status="failed",
                error_message=str(exc)[:500],
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        logger.exception("Time automation execution failed: automation_id=%s", automation.id)
        return False


def run_time_automation_scheduler_cycle(window_start: datetime, window_end: datetime, db: Session) -> int:
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=UTC)
    else:
        window_start = window_start.astimezone(UTC)

    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=UTC)
    else:
        window_end = window_end.astimezone(UTC)

    if window_end <= window_start:
        return 0

    automations = db.query(Automation).filter(Automation.trigger_type == AutomationTriggerType.TIME).all()

    executed_count = 0
    for automation in automations:
        for scheduled_for in _iter_due_slots(automation, window_start, window_end):
            if _try_execute_due_automation(db, automation, scheduled_for):
                executed_count += 1

    return executed_count


def run_time_scheduler_iteration(db: Session, now: datetime | None = None) -> int:
    reference_time = now.astimezone(UTC) if now is not None else utc_now()
    state = _get_or_create_scheduler_state(db, reference_time)

    try:
        window_start = parse_utc_iso(state.last_checked_at)
    except Exception:
        window_start = reference_time - timedelta(hours=_recovery_hours())

    if window_start > reference_time:
        window_start = reference_time - timedelta(seconds=_poll_seconds())

    executed_count = run_time_automation_scheduler_cycle(window_start, reference_time, db=db)
    state.last_checked_at = to_utc_iso(reference_time)
    db.commit()

    return executed_count


class TimeAutomationScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="time-automation-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while True:
            db = SessionLocal()
            try:
                executed = run_time_scheduler_iteration(db)
                if executed:
                    logger.info("Executed %s time-based automations", executed)
            except asyncio.CancelledError:
                db.close()
                raise
            except Exception:
                logger.exception("Automation scheduler iteration failed")
            finally:
                db.close()

            await asyncio.sleep(_poll_seconds())


scheduler = TimeAutomationScheduler()
