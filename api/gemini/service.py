"""
Groq AI service for smart home control.
Handles chat interactions, function calling, and device control orchestration.
Uses Groq cloud with llama-3.1-8b-instant model.
"""
import os
import json
import logging
from typing import Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from dotenv import load_dotenv, find_dotenv
import pathlib
import traceback

# Ensure .env is loaded when this module is imported. Use find_dotenv()
# so the .env file is located even if the current working directory differs.
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)

# Basic diagnostic information to help debug missing config at runtime.
try:
    _dotenv_file = pathlib.Path(dotenv_path).resolve() if dotenv_path else None
except Exception:
    _dotenv_file = None

logger = logging.getLogger(__name__)
logger.debug(f".env resolved to: {_dotenv_file}")
logger.debug("GROQ_API_KEY present in environment: %s", bool(os.getenv("GROQ_API_KEY")))

try:
    from groq import AsyncGroq
except Exception:
    AsyncGroq = None

from api.gemini.models import ChatMessage
from api.gemini.tools import get_groq_tools
from api.gemini.time_parser import parse_automation_schedule
from database.models import (
    User, House, Room, Device, Automation, AutomationExecution,
    EnergyHistory, RoomEnergyHistory, DeviceEnergyHistory
)
from database.enums import AutomationTriggerType, DeviceType
from api.devices.endpoints import DeviceEndpoints
from api.automations.endpoints import AutomationEndpoints
from api.house.endpoints import HouseEndpoints
from api.energy.endpoints import EnergyEndpoints


logger = logging.getLogger(__name__)


class GeminiService:
    """Service for Groq AI integration with smart home control.
    
    Class name kept as GeminiService to maintain backward compatibility
    with endpoints and other modules that reference it.
    """
    
    def __init__(self):
        """Initialize Groq client."""
        # Diagnostic field to report why initialization failed (if any)
        self.init_error: Optional[str] = None
        self.model_name = "llama-3.3-70b-versatile"
        
        api_key = os.getenv("GROQ_API_KEY")

        # Strip accidental surrounding quotes that sometimes appear in .env values
        if isinstance(api_key, str) and len(api_key) >= 2 and (
            (api_key.startswith('"') and api_key.endswith('"')) or
            (api_key.startswith("'") and api_key.endswith("'"))
        ):
            api_key = api_key[1:-1]

        if not api_key:
            self.init_error = "no_api_key"
            logger.warning("GROQ_API_KEY not set. AI features will be disabled.")
            self.model = None
            return
        
        if AsyncGroq is None:
            self.init_error = "groq_not_installed"
            logger.warning("groq SDK not installed; AI features disabled.")
            self.model = None
            return

        try:
            self.client = AsyncGroq(api_key=api_key)
            # Store a truthy sentinel so existing checks like `if self.model` still work.
            self.model = True
            logger.info("Groq AI initialized successfully with model %s", self.model_name)
        except Exception as e:
            tb = traceback.format_exc()
            self.init_error = {
                "error": str(e),
                "traceback": tb,
            }
            logger.error("Failed to initialize Groq client", exc_info=True)
            self.model = None
        
    def _get_system_prompt(self, user_id: UUID, db: Session) -> str:
        """Generate system prompt with user context."""
        user = db.query(User).filter(User.id == user_id).first()
        houses = db.query(House).filter(House.user_id == user_id).all()
        
        house_info = "\n".join([
            f"- {h.name} (ID: {h.id})"
            for h in houses
        ])
        
        return f"""You are a helpful AI assistant for a smart home system. 
        
The user {user.username} has the following houses:
{house_info}

You have access to tools to control devices, create automations, and manage the smart home.

When the user asks you to do something:
1. Use the available tools to help them
2. For device operations, you may need to call find_device_by_name first to locate devices by name
3. When creating time-based automations, always convert natural language times to HH:MM format (e.g., "at noon" -> "12:00")
4. Auto-execute all function calls without asking for confirmation
5. Be concise and direct in your responses
6. Call ONE function at a time, wait for its result, then decide the next step
7. Always use proper boolean values (true/false), never strings
8. Do not modify the name of the parameters, keep all the parameters from the default value even though it is not requested to be modified.

Current date/time context: Use this when interpreting user requests about timing."""
    
    async def chat(
        self,
        user_id: UUID,
        user_message: str,
        chat_history: list[ChatMessage],
        db: Session,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Process a chat message and execute function calls.
        
        Args:
            user_id: UUID of the user
            user_message: The user's message
            chat_history: List of previous messages in conversation
            db: Database session
            
        Returns:
            Tuple of (response_text, executed_functions)
        """
        if self.model is None:
            return "AI is not configured. Please set GROQ_API_KEY environment variable.", []
        
        try:
            # Build conversation history for Groq (OpenAI-compatible format)
            system_prompt = self._get_system_prompt(user_id, db)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt}
            ]
            
            for msg in chat_history:
                role = "user" if msg.role.lower() == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            tools = get_groq_tools()
            executed_functions = []
            response_text = ""
            
            # Function-calling loop: keep going until the model returns a
            # text-only response with no more tool calls.
            max_iterations = 10  # Safety limit to prevent infinite loops
            for _iteration in range(max_iterations):
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                )
                
                choice = response.choices[0]
                assistant_message = choice.message
                
                # If there are no tool calls, extract text and break
                if not assistant_message.tool_calls:
                    response_text = assistant_message.content or ""
                    break
                
                # Append the assistant message (with tool calls) to conversation
                # We need to serialize it properly for the messages list
                tool_calls_serialized = []
                for tc in assistant_message.tool_calls:
                    tool_calls_serialized.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    })
                
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": tool_calls_serialized,
                })
                
                # Execute each tool call and collect results
                for tc in assistant_message.tool_calls:
                    func_name = tc.function.name
                    func_args = json.loads(tc.function.arguments)
                    
                    logger.info(f"Executing function call: {func_name}({func_args})")
                    
                    func_result = await self._execute_function_call(
                        user_id=user_id,
                        function_name=func_name,
                        function_args=func_args,
                        db=db,
                    )
                    
                    executed_functions.append({
                        "name": func_name,
                        "args": func_args,
                        "result": func_result,
                    })
                    
                    # Append tool result message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(func_result),
                    })
                
                # Reset response_text so we pick up the new text from next turn
                response_text = ""
            
            return response_text or "Done.", executed_functions
            
        except Exception as e:
            logger.error(f"Error in AI chat: {e}")
            raise
    
    @staticmethod
    def _sanitize_uuid(value: str) -> str:
        """Strip curly braces and whitespace that the LLM sometimes adds to UUIDs."""
        return value.strip().strip("{}")

    async def _execute_function_call(
        self,
        user_id: UUID,
        function_name: str,
        function_args: dict[str, Any],
        db: Session,
    ) -> str:
        """
        Execute a function call from the AI model.
        
        Args:
            user_id: UUID of the user
            function_name: Name of the function to execute
            function_args: Arguments for the function
            db: Database session
            
        Returns:
            String result of function execution
        """
        try:
            if function_name == "get_houses":
                return self._get_houses(user_id, db)
            
            elif function_name == "get_rooms":
                house_id = UUID(self._sanitize_uuid(function_args["house_id"]))
                return self._get_rooms(user_id, house_id, db)
            
            elif function_name == "get_devices":
                house_id = UUID(self._sanitize_uuid(function_args["house_id"]))
                room_id = function_args.get("room_id")
                if room_id:
                    room_id = UUID(self._sanitize_uuid(room_id))
                return self._get_devices(user_id, house_id, room_id, db)
            
            elif function_name == "toggle_device":
                device_id = UUID(self._sanitize_uuid(function_args["device_id"]))
                turn_on = function_args["turn_on"]
                return self._toggle_device(user_id, device_id, turn_on, db)
            
            elif function_name == "set_device_parameters":
                device_id = UUID(self._sanitize_uuid(function_args["device_id"]))
                parameters = function_args["parameters"]
                return self._set_device_parameters(user_id, device_id, parameters, db)
            
            elif function_name == "create_time_automation":
                return self._create_time_automation(user_id, function_args, db)
            
            elif function_name == "create_temperature_automation":
                device_id = UUID(self._sanitize_uuid(function_args["device_id"]))
                return self._create_automation(
                    user_id=user_id,
                    device_id=device_id,
                    name=function_args["name"],
                    trigger_type=AutomationTriggerType.TEMPERATURE,
                    trigger_value=function_args["trigger_value"],
                    turn_on=function_args.get("turn_on", True),
                    parameters=function_args.get("parameters"),
                    db=db,
                )
            
            elif function_name == "create_light_automation":
                device_id = UUID(self._sanitize_uuid(function_args["device_id"]))
                return self._create_automation(
                    user_id=user_id,
                    device_id=device_id,
                    name=function_args["name"],
                    trigger_type=AutomationTriggerType.LUX,
                    trigger_value=function_args["trigger_value"],
                    turn_on=function_args.get("turn_on", False),
                    parameters=function_args.get("parameters"),
                    db=db,
                )
            
            elif function_name == "update_automation":
                automation_id = UUID(self._sanitize_uuid(function_args["automation_id"]))
                return self._update_automation(user_id, automation_id, function_args, db)
            
            elif function_name == "delete_automation":
                automation_id = UUID(self._sanitize_uuid(function_args["automation_id"]))
                return self._delete_automation(user_id, automation_id, db)
            
            elif function_name == "get_automations":
                device_id = UUID(self._sanitize_uuid(function_args["device_id"]))
                return self._get_automations(user_id, device_id, db)
            
            elif function_name == "get_energy_status":
                house_id = UUID(self._sanitize_uuid(function_args["house_id"]))
                room_id = function_args.get("room_id")
                device_id = function_args.get("device_id")
                if room_id:
                    room_id = UUID(self._sanitize_uuid(room_id))
                if device_id:
                    device_id = UUID(self._sanitize_uuid(device_id))
                return self._get_energy_status(user_id, house_id, room_id, device_id, db)
            
            elif function_name == "find_device_by_name":
                device_name = function_args["device_name"]
                house_id = function_args.get("house_id")
                if house_id:
                    house_id = UUID(self._sanitize_uuid(house_id))
                return self._find_device_by_name(user_id, device_name, house_id, db)
            
            else:
                return f"Unknown function: {function_name}"
        
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return f"Error executing {function_name}: {str(e)}"
    
    # ============== Device Functions ==============
    
    def _get_houses(self, user_id: UUID, db: Session) -> str:
        """Get all houses for a user."""
        houses = db.query(House).filter(House.user_id == user_id).all()
        if not houses:
            return "No houses found."
        
        result = "Your houses:\\n"
        for house in houses:
            result += f"- {house.name} (ID: {house.id})\\n"
        return result
    
    def _get_rooms(self, user_id: UUID, house_id: UUID, db: Session) -> str:
        """Get all rooms in a house."""
        house = db.query(House).filter(
            and_(House.id == house_id, House.user_id == user_id)
        ).first()
        
        if not house:
            return "House not found."
        
        rooms = db.query(Room).filter(Room.house_id == house_id).all()
        if not rooms:
            return f"No rooms in {house.name}."
        
        result = f"Rooms in {house.name}:\\n"
        for room in rooms:
            result += f"- {room.name} (ID: {room.id}) - Type: {room.room_type}\\n"
        return result
    
    def _get_devices(
        self,
        user_id: UUID,
        house_id: UUID,
        room_id: Optional[UUID],
        db: Session,
    ) -> str:
        """Get devices in a house or room."""
        house = db.query(House).filter(
            and_(House.id == house_id, House.user_id == user_id)
        ).first()
        
        if not house:
            return "House not found."
        
        query = db.query(Device).join(Room).filter(Room.house_id == house_id)
        
        if room_id:
            query = query.filter(Device.room_id == room_id)
        
        devices = query.all()
        
        if not devices:
            location = f"in room {room_id}" if room_id else f"in {house.name}"
            return f"No devices found {location}."
        
        result = "Devices:\\n"
        for device in devices:
            params = device.parameters or {}
            status = "ON" if params.get("status", False) else "OFF"
            result += f"- {device.name} ({device.type}) - {status} (ID: {device.id})\\n"
        return result
    
    def _toggle_device(self, user_id: UUID, device_id: UUID, turn_on: bool, db: Session) -> str:
        """Turn a device on or off."""
        device = self._verify_device_ownership(user_id, device_id, db)
        if isinstance(device, str):  # Error message
            return device
        
        # Status lives inside the JSON `parameters` column, not as a top-level attribute.
        params = dict(device.parameters or {})
        params["status"] = turn_on
        device.parameters = params
        db.commit()
        
        action = "turned on" if turn_on else "turned off"
        return f"{device.name} {action}."
    
    def _set_device_parameters(
        self,
        user_id: UUID,
        device_id: UUID,
        parameters: dict[str, Any],
        db: Session,
    ) -> str:
        """Set parameters on a device."""
        device = self._verify_device_ownership(user_id, device_id, db)
        if isinstance(device, str):  # Error message
            return device
        
        device.parameters = parameters
        db.commit()
        
        return f"Set {device.name} parameters to {parameters}."
    
    def _find_device_by_name(
        self,
        user_id: UUID,
        device_name: str,
        house_id: Optional[UUID],
        db: Session,
    ) -> str:
        """Find a device by name."""
        query = db.query(Device).join(Room).join(House).filter(
            House.user_id == user_id
        )
        
        if house_id:
            query = query.filter(House.id == house_id)
        
        # Search by name (case-insensitive, partial match)
        devices = query.filter(
            func.lower(Device.name).contains(device_name.lower())
        ).all()
        
        if not devices:
            return f"No devices found matching '{device_name}'."
        
        if len(devices) == 1:
            return f"Found: {devices[0].name} (ID: {devices[0].id})"
        
        result = f"Found {len(devices)} devices matching '{device_name}':\\n"
        for device in devices:
            result += f"- {device.name} (ID: {device.id})\\n"
        return result
    
    # ============== Automation Functions ==============
    
    def _create_time_automation(
        self,
        user_id: UUID,
        args: dict[str, Any],
        db: Session,
    ) -> str:
        """Create a time-based automation."""
        device_id = UUID(self._sanitize_uuid(args["device_id"]))
        
        # Parse natural language time if needed
        trigger_value = args["trigger_value"]
        execution_day = args.get("execution_day")
        
        return self._create_automation(
            user_id=user_id,
            device_id=device_id,
            name=args["name"],
            trigger_type=AutomationTriggerType.TIME,
            trigger_value=trigger_value,
            turn_on=args.get("turn_on", True),
            parameters=args.get("parameters"),
            execution_day=execution_day,
            db=db,
        )
    
    def _create_automation(
        self,
        user_id: UUID,
        device_id: UUID,
        name: str,
        trigger_type: AutomationTriggerType,
        trigger_value: str,
        turn_on: bool,
        parameters: Optional[dict[str, Any]],
        execution_day: Optional[int] = None,
        db: Session = None,
    ) -> str:
        """Create an automation."""
        device = self._verify_device_ownership(user_id, device_id, db)
        if isinstance(device, str):  # Error message
            return device
        
        automation = Automation(
            name=name,
            device_id=device_id,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            execution_day=execution_day,
            turn_on=turn_on,
            parameters=parameters or {},
        )
        
        db.add(automation)
        db.commit()
        
        return f"Created automation '{name}' for {device.name}."
    
    def _update_automation(
        self,
        user_id: UUID,
        automation_id: UUID,
        args: dict[str, Any],
        db: Session,
    ) -> str:
        """Update an automation."""
        automation = db.query(Automation).filter(Automation.id == automation_id).first()
        
        if not automation:
            return "Automation not found."
        
        # Verify ownership
        device = db.query(Device).filter(Device.id == automation.device_id).first()
        if not device:
            return "Device not found."
        
        room = db.query(Room).filter(Room.id == device.room_id).first()
        house = db.query(House).filter(and_(
            House.id == room.house_id,
            House.user_id == user_id
        )).first()
        
        if not house:
            return "Access denied."
        
        # Update fields
        if "name" in args:
            automation.name = args["name"]
        if "trigger_value" in args:
            automation.trigger_value = args["trigger_value"]
        if "turn_on" in args:
            automation.turn_on = args["turn_on"]
        
        db.commit()
        return f"Updated automation '{automation.name}'."
    
    def _delete_automation(self, user_id: UUID, automation_id: UUID, db: Session) -> str:
        """Delete an automation."""
        automation = db.query(Automation).filter(Automation.id == automation_id).first()
        
        if not automation:
            return "Automation not found."
        
        # Verify ownership
        device = db.query(Device).filter(Device.id == automation.device_id).first()
        room = db.query(Room).filter(Room.id == device.room_id).first()
        house = db.query(House).filter(and_(
            House.id == room.house_id,
            House.user_id == user_id
        )).first()
        
        if not house:
            return "Access denied."
        
        automation_name = automation.name
        db.delete(automation)
        db.commit()
        return f"Deleted automation '{automation_name}'."
    
    def _get_automations(self, user_id: UUID, device_id: UUID, db: Session) -> str:
        """Get automations for a device."""
        device = self._verify_device_ownership(user_id, device_id, db)
        if isinstance(device, str):  # Error message
            return device
        
        automations = db.query(Automation).filter(
            Automation.device_id == device_id
        ).all()
        
        if not automations:
            return f"No automations for {device.name}."
        
        result = f"Automations for {device.name}:\\n"
        for auto in automations:
            result += f"- {auto.name} ({auto.trigger_type.value}) - {auto.trigger_value} (ID: {auto.id})\\n"
        return result
    
    # ============== Energy Functions ==============
    
    def _get_energy_status(
        self,
        user_id: UUID,
        house_id: UUID,
        room_id: Optional[UUID],
        device_id: Optional[UUID],
        db: Session,
    ) -> str:
        """Get energy consumption status."""
        house = db.query(House).filter(
            and_(House.id == house_id, House.user_id == user_id)
        ).first()
        
        if not house:
            return "House not found."
        # If a specific device is requested, use device energy history
        if device_id:
            entries = db.query(DeviceEnergyHistory).filter(DeviceEnergyHistory.device_id == device_id).all()
            if not entries:
                return "No energy data available for that device."
            total_watts = sum(e.estimated_watts for e in entries)
            device = db.query(Device).filter(Device.id == device_id).first()
            result = f"Energy consumption for device {device.name}:\\n"
            result += f"Total (last samples): {total_watts:.2f}W\\n"
            for e in entries[:10]:
                result += f"- {e.hour_slot}: {e.estimated_watts:.2f}W (on: {e.is_on})\\n"
            return result

        # If a room is requested, aggregate device energy in that room
        if room_id:
            entries = (
                db.query(DeviceEnergyHistory)
                .join(Device)
                .filter(Device.room_id == room_id)
                .all()
            )
            if not entries:
                return "No energy data available for that room."
            total_watts = sum(e.estimated_watts for e in entries)
            result = f"Energy consumption for room (ID: {room_id}):\\n"
            result += f"Total (last samples): {total_watts:.2f}W\\n"
            for e in entries[:10]:
                dev = db.query(Device).filter(Device.id == e.device_id).first()
                result += f"- {dev.name}: {e.estimated_watts:.2f}W at {e.hour_slot}\\n"
            return result

        # Otherwise, summarize recent device energy entries for the whole house
        entries = (
            db.query(DeviceEnergyHistory)
            .join(Device).join(Room)
            .filter(Room.house_id == house_id)
            .all()
        )
        if not entries:
            return "No energy data available."
        total_watts = sum(e.estimated_watts for e in entries)
        result = f"Energy consumption for {house.name}:\\n"
        result += f"Total (last samples): {total_watts:.2f}W\\n"
        # Group by device and list a few
        seen = set()
        for e in entries[:10]:
            dev = db.query(Device).filter(Device.id == e.device_id).first()
            if dev and dev.id not in seen:
                seen.add(dev.id)
                result += f"- {dev.name}: {e.estimated_watts:.2f}W (sample {e.hour_slot})\\n"
        return result
    
    # ============== Helper Functions ==============
    
    def _verify_device_ownership(
        self,
        user_id: UUID,
        device_id: UUID,
        db: Session,
    ) -> Optional[Device] | str:
        """Verify that the user owns the device."""
        device = db.query(Device).filter(Device.id == device_id).first()
        
        if not device:
            return "Device not found."
        
        room = db.query(Room).filter(Room.id == device.room_id).first()
        house = db.query(House).filter(and_(
            House.id == room.house_id,
            House.user_id == user_id
        )).first()
        
        if not house:
            return "Access denied."
        
        return device
