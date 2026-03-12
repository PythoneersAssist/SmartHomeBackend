
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, Notification
from api.notifications.models import CreateNotificationModel, UpdateNotificationModel
from api.auth.endpoints import get_current_user

router = APIRouter(prefix="/notifications")

@cbv(router)
class NotificationEndpoints:
    db: Session = Depends(get_db)

    @router.post("/create", tags=["notification"])
    def create_notification(self, data: CreateNotificationModel, current_user: Annotated[User, Depends(get_current_user)]):
        self.db.add(Notification(
            title=data.title,
            message=data.message,
            created_at=str(datetime.now()),
            user=current_user,
        ))
        self.db.commit()

        return JSONResponse(
            content={"message": "Notification created successfully"},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get", tags=["notification"])
    def get_all_notifications(self, current_user: Annotated[User, Depends(get_current_user)]):
        notifications = (
            self.db.query(Notification)
            .filter(Notification.user_id == current_user.id)
            .all()
        )

        data = []
        for n in notifications:
            data.append({
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at,
            })

        return JSONResponse(
            content={"message": f"Retrieved {len(data)} notifications", "notifications": data},
            status_code=status.HTTP_200_OK
        )

    @router.get("/unread_count", tags=["notification"])
    def get_unread_count(self, current_user: Annotated[User, Depends(get_current_user)]):
        count = (
            self.db.query(Notification)
            .filter(Notification.user_id == current_user.id, Notification.is_read == False)
            .count()
        )

        return JSONResponse(
            content={"unread_count": count},
            status_code=status.HTTP_200_OK
        )

    @router.patch("/mark_read/{notification_id}", tags=["notification"])
    def mark_notification_read(self, notification_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        if notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this notification"
            )

        notification.is_read = True
        self.db.commit()

        return JSONResponse(
            content={"message": "Notification marked as read"},
            status_code=status.HTTP_200_OK
        )

    @router.patch("/mark_all_read", tags=["notification"])
    def mark_all_notifications_read(self, current_user: Annotated[User, Depends(get_current_user)]):
        self.db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({"is_read": True})
        self.db.commit()

        return JSONResponse(
            content={"message": "All notifications marked as read"},
            status_code=status.HTTP_200_OK
        )

    @router.delete("/delete/{notification_id}", tags=["notification"])
    def delete_notification(self, notification_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        if notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this notification"
            )

        self.db.delete(notification)
        self.db.commit()

        return JSONResponse(
            content={"message": "Notification deleted successfully"},
            status_code=status.HTTP_200_OK
        )