"""
WebSocket endpoint for Gemini chat interface.
Provides real-time chat with function calling capabilities.
"""
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
import os

import api.gemini.service as gemini_service_module

from database.database import get_db
from utils.security import verify_token
from api.gemini.service import GeminiService
from api.gemini.models import ChatMessage, ChatRequest, ChatResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gemini", tags=["gemini"])

# In-memory chat history storage per user
# In production, consider using Redis or database
chat_histories: dict[UUID, list[ChatMessage]] = {}
gemini_service = GeminiService()


@router.get("/status")
def gemini_status():
    """Return diagnostic status about AI (Groq) configuration for debugging."""
    env_key = os.getenv("GROQ_API_KEY")
    masked = None
    if env_key:
        if len(env_key) > 8:
            masked = env_key[:4] + "..." + env_key[-4:]
        else:
            masked = "****"

    return {
        "env_resolved": str(getattr(gemini_service_module, "_dotenv_file", None)),
        "groq_key_present": bool(env_key),
        "groq_key_masked": masked,
        "initialized": bool(gemini_service.model),
        "init_error": getattr(gemini_service, "init_error", None),
    }


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for Gemini chat.
    
    Query parameters:
        token: JWT authentication token
    
    Message format (JSON):
        {
            "message": "turn on my lights at 12pm"
        }
    
    Response format (JSON):
        {
            "role": "assistant",
            "content": "I've turned on your lights and created a daily automation at 12:00 PM.",
            "function_calls": [
                {
                    "name": "find_device_by_name",
                    "args": {"device_name": "lights"},
                    "result": "Found: Living room light (ID: ...)"
                },
                {
                    "name": "create_time_automation",
                    "args": {...},
                    "result": "Created automation..."
                }
            ]
        }
    """
    # Authenticate user
    try:
        payload = verify_token(token)
        user_id = UUID(payload.get("sub"))
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await websocket.accept()
    logger.info(f"User {user_id} connected to Gemini chat")
    
    # Initialize chat history for this user session if not exists
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()
            
            if not user_message:
                await websocket.send_json({
                    "role": "assistant",
                    "content": "Please enter a message.",
                    "function_calls": None,
                })
                continue
            
            # Add user message to history
            chat_histories[user_id].append(ChatMessage(
                role="user",
                content=user_message,
            ))
            
            # Get response from Gemini
            try:
                response_text, executed_functions = await gemini_service.chat(
                    user_id=user_id,
                    user_message=user_message,
                    chat_history=chat_histories[user_id],
                    db=db,
                )
                
                # Add assistant response to history
                chat_histories[user_id].append(ChatMessage(
                    role="assistant",
                    content=response_text,
                ))
                
                # Send response to client
                await websocket.send_json({
                    "role": "assistant",
                    "content": response_text,
                    "function_calls": executed_functions if executed_functions else None,
                })
                
            except Exception as e:
                logger.error(f"Error processing chat: {e}")
                await websocket.send_json({
                    "role": "assistant",
                    "content": f"An error occurred: {str(e)}",
                    "function_calls": None,
                })
    
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from Gemini chat")
        # Optional: Optionally clean up old chat histories
        # del chat_histories[user_id]
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")


@router.post("/clear-history")
async def clear_chat_history(
    token: str = Query(...),
):
    """
    Clear chat history for current user.
    Useful for starting fresh conversations.
    """
    try:
        payload = verify_token(token)
        user_id = UUID(payload.get("sub"))
        
        if user_id in chat_histories:
            chat_histories[user_id] = []
        
        return {"message": "Chat history cleared."}
    
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return {"error": "Failed to clear history"}, 400


@router.get("/history")
async def get_chat_history(
    token: str = Query(...),
    limit: Optional[int] = Query(50, ge=1, le=500),
):
    """
    Get recent chat history for current user.
    
    Query parameters:
        token: JWT authentication token
        limit: Maximum number of messages to return (default: 50, max: 500)
    """
    try:
        payload = verify_token(token)
        user_id = UUID(payload.get("sub"))
        
        history = chat_histories.get(user_id, [])
        
        # Return last 'limit' messages
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history[-limit:]
        ]
        
        return {"messages": messages}
    
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {"error": "Failed to fetch history"}, 400
