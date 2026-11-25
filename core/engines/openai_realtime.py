"""
OpenAI Realtime API Engine for Closer Assistant

Implements real-time speech-to-speech conversation using OpenAI's Realtime API.
Supports interruptions, function calling, and natural turn-taking.

Documentation: https://platform.openai.com/docs/api-reference/realtime
"""
import asyncio
import json
import base64
import ssl
import time
from typing import Dict, Any, Optional
import certifi
from websockets import connect, WebSocketClientProtocol
import logging

from .base_engine import (
    BaseEngine, EngineType, SessionConfig, AudioChunk, 
    ConversationTurn, TurnType
)

logger = logging.getLogger(__name__)


class OpenAIRealtimeEngine(BaseEngine):
    """
    OpenAI Realtime API engine implementation.
    
    Features:
    - Direct speech-to-speech (no STT/TTS pipeline)
    - Natural interruption handling
    - Function calling for actions
    - Low latency (<200ms typical)
    - Multiple model options (gpt-4o-realtime, gpt-4o-mini-realtime)
    """
    
    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    MODELS = {
        "standard": "gpt-4o-realtime-preview-2024-10-01",
        "mini": "gpt-4o-mini-realtime-preview-2024-12-17"
    }
    VOICES = ["alloy", "echo", "shimmer", "sage", "ash", "coral"]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or config.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model = config.get("model", "mini")  # "standard" or "mini"
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.conversation_history: list[ConversationTurn] = []
        self.current_response_id: Optional[str] = None
        self.latency_metrics = []
        
    @property
    def engine_type(self) -> EngineType:
        return EngineType.OPENAI_REALTIME
    
    @property
    def supports_realtime_audio(self) -> bool:
        return True
    
    @property
    def supports_interruptions(self) -> bool:
        return True
    
    @property
    def supports_function_calling(self) -> bool:
        return True
    
    async def connect(self, session_config: SessionConfig) -> str:
        """
        Connect to OpenAI Realtime API via WebSocket.
        """
        self._validate_session_config(session_config)
        
        try:
            # Connect to WebSocket
            model_name = self.MODELS[self.model]
            url = f"{self.WEBSOCKET_URL}?model={model_name}"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self.websocket = await connect(url, additional_headers=headers, ssl=ssl_context)
            self.is_connected = True
            
            # Configure session
            await self._configure_session(session_config)
            
            # Start listening for events
            asyncio.create_task(self._listen_for_events())
            
            self.session_id = f"openai_{int(time.time())}"
            logger.info(f"Connected to OpenAI Realtime API: {self.session_id}")
            
            return self.session_id
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime: {e}")
            raise
    
    async def _configure_session(self, config: SessionConfig) -> None:
        """
        Send session.update event to configure the conversation.
        """
        # Build system instructions from personality and knowledge
        system_instructions = self._build_system_instructions(config)
        
        # Choose voice
        voice = config.voice_id if config.voice_id in self.VOICES else "alloy"
        
        # Build tools/functions
        tools = self._build_tools(config.available_functions or [])
        
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": system_instructions,
                "voice": voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",  # Voice Activity Detection
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500  # Fast turn-taking
                },
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.8,
                "max_response_output_tokens": 4096
            }
        }
        
        await self.websocket.send(json.dumps(session_update))
        logger.info("Session configured with business personality and functions")
    
    def _build_system_instructions(self, config: SessionConfig) -> str:
        """
        Build system instructions from personality and business context.
        """
        instructions = []
        
        # Base identity
        worker_name = config.personality.get("name", "Assistant") if config.personality else "Assistant"
        business_name = config.knowledge_base.get("business_name", "the business") if config.knowledge_base else "the business"
        
        instructions.append(f"You are {worker_name}, a professional receptionist/assistant for {business_name}.")
        
        # Personality traits
        if config.personality:
            personality_desc = config.personality.get("description", "")
            if personality_desc:
                instructions.append(personality_desc)
            
            traits = config.personality.get("traits", [])
            if traits:
                instructions.append(f"Your personality traits: {', '.join(traits)}")
        
        # Communication style
        instructions.append("""
COMMUNICATION RULES:
- Keep responses SHORT and conversational (1-3 sentences max)
- Speak naturally as if on a phone call
- Never read long paragraphs
- Use casual, warm language
- Handle interruptions gracefully
- Ask one question at a time
- Confirm bookings clearly
        """.strip())
        
        # Business knowledge
        if config.knowledge_base:
            kb_summary = config.knowledge_base.get("summary", "")
            if kb_summary:
                instructions.append(f"\nBUSINESS INFORMATION:\n{kb_summary}")
        
        # Current context
        if config.context:
            context_str = json.dumps(config.context, indent=2)
            instructions.append(f"\nCURRENT CONTEXT:\n{context_str}")
        
        return "\n\n".join(instructions)
    
    def _build_tools(self, functions: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Convert function definitions to OpenAI tool format.
        """
        tools = []
        for func in functions:
            tool = {
                "type": "function",
                "name": func["name"],
                "description": func["description"],
                "parameters": func.get("parameters", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
            tools.append(tool)
        return tools
    
    async def _listen_for_events(self) -> None:
        """
        Listen for events from OpenAI Realtime API.
        """
        try:
            async for message in self.websocket:
                event = json.loads(message)
                await self._handle_event(event)
        except Exception as e:
            logger.error(f"Error in event listener: {e}")
            self.is_connected = False
            self._emit_event("error", {"error": str(e)})
    
    async def _handle_event(self, event: Dict[str, Any]) -> None:
        """
        Handle different event types from the API.
        """
        event_type = event.get("type")
        
        if event_type == "session.created":
            logger.info("Session created successfully")
            
        elif event_type == "conversation.item.created":
            # Track conversation turns
            item = event.get("item", {})
            logger.debug(f"Item created: {item.get('type')}")
            
        elif event_type == "response.audio.delta":
            # Stream audio output
            delta = event.get("delta")
            if delta:
                audio_data = base64.b64decode(delta)
                self._emit_event("audio_output", {
                    "audio": audio_data,
                    "format": "pcm16",
                    "sample_rate": 24000
                })
        
        elif event_type == "response.audio_transcript.delta":
            # Transcript of what assistant is saying
            delta = event.get("delta")
            if delta:
                self._emit_event("text_output", {"text": delta})
        
        elif event_type == "response.function_call_arguments.done":
            # Function call complete
            call_id = event.get("call_id")
            function_name = event.get("name")
            arguments = json.loads(event.get("arguments", "{}"))
            
            logger.info(f"Function call: {function_name}({arguments})")
            
            # Emit to business logic layer
            self._emit_event("function_call", {
                "call_id": call_id,
                "name": function_name,
                "arguments": arguments
            })
            
            # Execute function
            result = await self.execute_function(function_name, arguments)
            
            # Send result back
            await self._send_function_result(call_id, result)
        
        elif event_type == "response.done":
            # Turn complete
            response = event.get("response", {})
            self._emit_event("turn_complete", {"response": response})
            
            # Calculate latency
            if "usage" in response:
                self._emit_event("latency", {
                    "response_time_ms": response.get("response_time_ms"),
                    "usage": response.get("usage")
                })
        
        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"OpenAI error: {error}")
            self._emit_event("error", error)
        
        elif event_type == "input_audio_buffer.speech_started":
            # User started speaking
            logger.debug("User started speaking")
            
        elif event_type == "input_audio_buffer.speech_stopped":
            # User stopped speaking
            logger.debug("User stopped speaking")
    
    async def send_audio(self, audio_chunk: AudioChunk) -> None:
        """
        Send audio input from user to the API.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to OpenAI Realtime API")
        
        # Convert audio to base64
        audio_b64 = base64.b64encode(audio_chunk.data).decode('utf-8')
        
        # Send as audio append event
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        
        await self.websocket.send(json.dumps(event))
    
    async def send_text(self, text: str) -> None:
        """
        Send text input (for chat channels).
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to OpenAI Realtime API")
        
        # Create conversation item
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text
                    }
                ]
            }
        }
        
        await self.websocket.send(json.dumps(event))
        
        # Trigger response
        await self._trigger_response()
    
    async def interrupt(self) -> None:
        """
        Interrupt the current assistant response.
        """
        if not self.is_connected:
            return
        
        # Send response.cancel
        event = {
            "type": "response.cancel"
        }
        
        await self.websocket.send(json.dumps(event))
        logger.info("Response interrupted")
    
    async def _trigger_response(self) -> None:
        """
        Tell the API to generate a response.
        """
        event = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "Respond naturally and conversationally."
            }
        }
        
        await self.websocket.send(json.dumps(event))
    
    async def _send_function_result(self, call_id: str, result: Dict[str, Any]) -> None:
        """
        Send function call result back to the API.
        """
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result)
            }
        }
        
        await self.websocket.send(json.dumps(event))
        
        # Trigger response to continue conversation
        await self._trigger_response()
    
    async def execute_function(
        self, 
        function_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute function - delegated to business logic layer.
        This is a pass-through; actual execution happens in actions/ modules.
        """
        # Business logic layer handles this via callback
        # This method just returns a placeholder
        return {
            "status": "delegated",
            "function": function_name,
            "arguments": arguments
        }
    
    async def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update conversation context dynamically.
        """
        # Send as conversation item
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Context update: {json.dumps(context)}"
                    }
                ]
            }
        }
        
        await self.websocket.send(json.dumps(event))
    
    def register_callback(self, event: str, callback) -> None:
        """Register event callback."""
        self.callbacks[event] = callback
    
    async def get_session_state(self) -> Dict[str, Any]:
        """Get current session state."""
        return {
            "session_id": self.session_id,
            "connected": self.is_connected,
            "model": self.MODELS[self.model],
            "conversation_length": len(self.conversation_history),
            "average_latency": sum(self.latency_metrics) / len(self.latency_metrics) if self.latency_metrics else 0
        }
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from OpenAI Realtime API")
