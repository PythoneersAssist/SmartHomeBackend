"""Tests for notification endpoints (/notifications/*)."""

from datetime import datetime, timezone
from uuid import UUID

from database.models import Notification
from tests.conftest import (
    TEST_USER,
    TEST_USER_2,
    auth_header,
    create_test_user,
    create_user_and_login,
    get_auth_token,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_notification(db_session, user_id: str, title: str, *, is_read: bool = False) -> Notification:
    notification = Notification(
        title=title,
        message=f"{title} message",
        is_read=is_read,
        created_at=_utc_now_iso(),
        user_id=UUID(user_id),
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification


class TestNotifications:
    def test_get_notifications_returns_only_current_user(self, client, db_session):
        _, token_1 = create_user_and_login(client, TEST_USER)

        create_test_user(client, TEST_USER_2)
        token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        user_1_id = client.get("/user/get", headers=auth_header(token_1)).json()["id"]
        user_2_id = client.get("/user/get", headers=auth_header(token_2)).json()["id"]

        notif_1 = create_notification(db_session, user_1_id, "User1 A")
        notif_2 = create_notification(db_session, user_1_id, "User1 B")
        notif_other = create_notification(db_session, user_2_id, "User2 A")

        response = client.get("/notifications/get", headers=auth_header(token_1))
        assert response.status_code == 200

        notifications = response.json()["notifications"]
        ids = {n["id"] for n in notifications}

        assert str(notif_1.id) in ids
        assert str(notif_2.id) in ids
        assert str(notif_other.id) not in ids

    def test_get_unread_count(self, client, db_session):
        _, token = create_user_and_login(client)
        user_id = client.get("/user/get", headers=auth_header(token)).json()["id"]

        create_notification(db_session, user_id, "Unread 1", is_read=False)
        create_notification(db_session, user_id, "Unread 2", is_read=False)
        create_notification(db_session, user_id, "Read 1", is_read=True)

        response = client.get("/notifications/unread_count", headers=auth_header(token))
        assert response.status_code == 200
        assert response.json()["unread_count"] == 2

    def test_mark_notification_read_and_ownership(self, client, db_session):
        _, token_1 = create_user_and_login(client, TEST_USER)
        user_1_id = client.get("/user/get", headers=auth_header(token_1)).json()["id"]

        create_test_user(client, TEST_USER_2)
        token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        notification = create_notification(db_session, user_1_id, "Needs Read", is_read=False)

        mark_response = client.patch(
            f"/notifications/mark_read/{notification.id}",
            headers=auth_header(token_1),
        )
        assert mark_response.status_code == 200

        refreshed = db_session.query(Notification).filter(Notification.id == notification.id).first()
        assert refreshed is not None
        assert refreshed.is_read is True

        forbidden_response = client.patch(
            f"/notifications/mark_read/{notification.id}",
            headers=auth_header(token_2),
        )
        assert forbidden_response.status_code == 404

    def test_mark_all_read_marks_only_current_user(self, client, db_session):
        _, token_1 = create_user_and_login(client, TEST_USER)
        user_1_id = client.get("/user/get", headers=auth_header(token_1)).json()["id"]

        create_test_user(client, TEST_USER_2)
        token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])
        user_2_id = client.get("/user/get", headers=auth_header(token_2)).json()["id"]

        create_notification(db_session, user_1_id, "U1 Unread A", is_read=False)
        create_notification(db_session, user_1_id, "U1 Unread B", is_read=False)
        create_notification(db_session, user_2_id, "U2 Unread", is_read=False)

        response = client.patch("/notifications/mark_all_read", headers=auth_header(token_1))
        assert response.status_code == 200

        user_1_unread = (
            db_session.query(Notification)
            .filter(Notification.user_id == UUID(user_1_id), Notification.is_read.is_(False))
            .count()
        )
        user_2_unread = (
            db_session.query(Notification)
            .filter(Notification.user_id == UUID(user_2_id), Notification.is_read.is_(False))
            .count()
        )

        assert user_1_unread == 0
        assert user_2_unread == 1

    def test_delete_notification(self, client, db_session):
        _, token = create_user_and_login(client)
        user_id = client.get("/user/get", headers=auth_header(token)).json()["id"]

        notification = create_notification(db_session, user_id, "Delete Me", is_read=False)

        response = client.delete(
            f"/notifications/delete/{notification.id}",
            headers=auth_header(token),
        )
        assert response.status_code == 200

        deleted = db_session.query(Notification).filter(Notification.id == notification.id).first()
        assert deleted is None
