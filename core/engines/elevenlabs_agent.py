"""
ElevenLabs Conversational AI Engine for Closer Assistant

Implements real-time conversational AI using ElevenLabs' agent platform.
Focuses on premium voice quality, custom voice cloning, and natural conversations.

Documentation: https://elevenlabs.io/docs/conversational-ai/overview
"""
import asyncio
import json
import base64
import time
from typing import Dict, Any, Optional
from websockets import connect, WebSocketClientProtocol
import httpx
import logging

from .base_engine import (
    BaseEngine, EngineType, SessionConfig, AudioChunk,
    ConversationTurn, TurnType
)

logger = logging.getLogger(__name__)


class ElevenLabsAgentEngine(BaseEngine):
    """
    ElevenLabs Conversational AI engine implementation.
    
    Features:
    - Premium voice quality with emotional range
    - Custom voice cloning for branded voices
    - Natural interruption handling
    - Tool/function calling
    - Multi-channel deployment (phone, web, WhatsApp)
    - Lower latency with optimized voices
    
    Best for: Businesses wanting distinctive, high-quality voices
    """
    
    WEBSOCKET_URL = "wss://api.elevenlabs.io/v1/convai/conversation"
    REST_API_BASE = "https://api.elevenlabs.io/v1"
    
    # Voice categories
    VOICE_CATEGORIES = {
        "professional": ["Rachel", "Domi", "Bella"],
        "casual": ["Josh", "Arnold", "Adam"],
        "warm": ["Elli", "Grace", "Emily"],
        "authoritative": "Dani",
        "energetic": ["Clyde", "Freya"]
    }
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or config.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required")
        
        self.agent_id: Optional[str] = None  # Created agent ID
        self.conversation_id: Optional[str] = None
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.http_client = httpx.AsyncClient(
            base_url=self.REST_API_BASE,
            headers={"xi-api-key": self.api_key}
        )
        self.conversation_history: list[ConversationTurn] = []
        self.latency_metrics = []
    
    @property
    def engine_type(self) -> EngineType:
        return EngineType.ELEVENLABS_AGENT
    
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
        Connect to ElevenLabs Conversational AI.
        
        Steps:
        1. Create or get agent configuration
        2. Start conversation session via WebSocket
        3. Configure tools and personality
        """
        self._validate_session_config(session_config)
        
        try:
            # Get or create agent
            self.agent_id = await self._ensure_agent_exists(session_config)
            
            # Connect via WebSocket
            url = f"{self.WEBSOCKET_URL}?agent_id={self.agent_id}"
            
            self.websocket = await connect(
                url,
                extra_headers={"xi-api-key": self.api_key}
            )
            self.is_connected = True
            
            # Start listening
            asyncio.create_task(self._listen_for_events())
            
            self.session_id = f"elevenlabs_{int(time.time())}"
            self.conversation_id = self.session_id
            
            logger.info(f"Connected to ElevenLabs Agent: {self.session_id}")
            
            return self.session_id
            
        except Exception as e:
            logger.error(f"Failed to connect to ElevenLabs: {e}")
            raise
    
    async def _ensure_agent_exists(self, config: SessionConfig) -> str:
        """
        Get existing agent or create new one with business configuration.
        """
        # Check if agent already exists for this worker
        worker_agent_id = config.context.get("elevenlabs_agent_id") if config.context else None
        
        if worker_agent_id:
            # Verify agent exists
            try:
                response = await self.http_client.get(f"/convai/agents/{worker_agent_id}")
                if response.status_code == 200:
                    return worker_agent_id
            except:
                pass
        
        # Create new agent
        return await self._create_agent(config)
    
    async def _create_agent(self, config: SessionConfig) -> str:
        """
        Create a new ElevenLabs conversational agent.
        """
        # Choose voice
        voice_id = await self._select_voice(config)
        
        # Build agent config
        agent_config = {
            "name": f"{config.worker_id}_agent",
            "conversation_config": {
                "agent": {
                    "prompt": {
                        "prompt": self._build_system_prompt(config),
                        "llm": "gpt-4"  # or "claude-3-5-sonnet"
                    },
                    "first_message": self._build_greeting(config),
                    "language": config.language or "en"
                },
                "tts": {
                    "voice_id": voice_id,
                    "model_id": "eleven_turbo_v2_5",  # Low latency
                    "optimize_streaming_latency": 4,
                    "stability": 0.5,
                    "similarity_boost": 0.8
                },
                "asr": {
                    "quality": "high",
                    "user_input_audio_format": "pcm_16000"
                },
                "turn_timeout": 0.5  # Fast turn-taking
            }
        }
        
        # Add tools/functions
        if config.available_functions:
            agent_config["conversation_config"]["tools"] = self._build_tools(
                config.available_functions
            )
        
        # Create agent
        response = await self.http_client.post("/convai/agents", json=agent_config)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to create agent: {response.text}")
        
        data = response.json()
        agent_id = data["agent_id"]
        
        logger.info(f"Created ElevenLabs agent: {agent_id}")
        return agent_id
    
    async def _select_voice(self, config: SessionConfig) -> str:
        """
        Select appropriate voice based on configuration.
        """
        # If custom voice ID provided
        if config.voice_id:
            return config.voice_id
        
        # Get voice personality preference
        personality_type = "professional"  # default
        if config.personality:
            personality_type = config.personality.get("voice_category", "professional")
        
        # List available voices
        response = await self.http_client.get("/voices")
        voices = response.json()["voices"]
        
        # Find matching voice
        recommended_names = self.VOICE_CATEGORIES.get(personality_type, ["Rachel"])
        
        for voice in voices:
            if voice["name"] in recommended_names:
                return voice["voice_id"]
        
        # Fallback to first available
        return voices[0]["voice_id"] if voices else None
    
    def _build_system_prompt(self, config: SessionConfig) -> str:
        """
        Build system prompt for the agent.
        """
        prompts = []
        
        # Identity
        worker_name = config.personality.get("name", "Assistant") if config.personality else "Assistant"
        business_name = config.knowledge_base.get("business_name", "the business") if config.knowledge_base else "the business"
        
        prompts.append(f"You are {worker_name}, working as a receptionist for {business_name}.")
        
        # Personality
        if config.personality:
            desc = config.personality.get("description", "")
            if desc:
                prompts.append(desc)
        
        # Communication style for phone calls
        prompts.append("""
PHONE CONVERSATION RULES:
- Keep responses SHORT (1-2 sentences)
- Speak naturally and conversationally
- Handle interruptions gracefully
- Ask ONE question at a time
- Confirm important details clearly
- Be warm but professional
- Don't read long scripts
        """.strip())
        
        # Business knowledge
        if config.knowledge_base:
            kb = config.knowledge_base.get("summary", "")
            if kb:
                prompts.append(f"\nBUSINESS INFO:\n{kb}")
        
        return "\n\n".join(prompts)
    
    def _build_greeting(self, config: SessionConfig) -> str:
        """
        Build first message/greeting.
        """
        worker_name = config.personality.get("name", "Assistant") if config.personality else "Assistant"
        business_name = config.knowledge_base.get("business_name", "us") if config.knowledge_base else "us"
        
        return f"Hello! This is {worker_name} from {business_name}. How can I help you today?"
    
    def _build_tools(self, functions: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Convert function definitions to ElevenLabs tool format.
        """
        tools = []
        for func in functions:
            tool = {
                "name": func["name"],
                "description": func["description"],
                "parameters": func.get("parameters", {}),
                "type": "webhook",  # or "client_tool" for client-side execution
                "webhook_config": {
                    "url": func.get("webhook_url", ""),
                    "method": "POST"
                }
            }
            tools.append(tool)
        return tools
    
    async def _listen_for_events(self) -> None:
        """
        Listen for events from ElevenLabs WebSocket.
        """
        try:
            async for message in self.websocket:
                # ElevenLabs sends both JSON and binary
                if isinstance(message, bytes):
                    # Audio data
                    await self._handle_audio_message(message)
                else:
                    # JSON event
                    event = json.loads(message)
                    await self._handle_json_event(event)
        except Exception as e:
            logger.error(f"Error in event listener: {e}")
            self.is_connected = False
            self._emit_event("error", {"error": str(e)})
    
    async def _handle_audio_message(self, audio_data: bytes) -> None:
        """
        Handle audio output from agent.
        """
        self._emit_event("audio_output", {
            "audio": audio_data,
            "format": "pcm16",
            "sample_rate": 16000  # ElevenLabs default
        })
    
    async def _handle_json_event(self, event: Dict[str, Any]) -> None:
        """
        Handle JSON events from ElevenLabs.
        """
        event_type = event.get("type")
        
        if event_type == "conversation_initiation_metadata":
            # Conversation started
            self.conversation_id = event.get("conversation_id")
            logger.info(f"Conversation started: {self.conversation_id}")
            
        elif event_type == "agent_response":
            # Agent is speaking
            text = event.get("text", "")
            self._emit_event("text_output", {"text": text})
            
        elif event_type == "user_transcript":
            # What user said
            text = event.get("text", "")
            logger.info(f"User said: {text}")
            
        elif event_type == "tool_call":
            # Function/tool call
            tool_name = event.get("tool_name")
            parameters = event.get("parameters", {})
            
            logger.info(f"Tool call: {tool_name}({parameters})")
            
            self._emit_event("function_call", {
                "name": tool_name,
                "arguments": parameters
            })
            
            # Execute and send result
            result = await self.execute_function(tool_name, parameters)
            await self._send_tool_result(tool_name, result)
            
        elif event_type == "interruption":
            # User interrupted
            logger.debug("User interrupted agent")
            
        elif event_type == "ping":
            # Send pong
            await self.websocket.send(json.dumps({"type": "pong"}))
            
        elif event_type == "error":
            error = event.get("message", "Unknown error")
            logger.error(f"ElevenLabs error: {error}")
            self._emit_event("error", {"error": error})
    
    async def send_audio(self, audio_chunk: AudioChunk) -> None:
        """
        Send audio input to ElevenLabs.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to ElevenLabs")
        
        # ElevenLabs expects raw PCM audio
        # Send as binary message
        await self.websocket.send(audio_chunk.data)
    
    async def send_text(self, text: str) -> None:
        """
        Send text input (for chat channels).
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to ElevenLabs")
        
        event = {
            "type": "user_message",
            "message": text
        }
        
        await self.websocket.send(json.dumps(event))
    
    async def interrupt(self) -> None:
        """
        Interrupt the agent's response.
        """
        if not self.is_connected:
            return
        
        event = {
            "type": "interrupt"
        }
        
        await self.websocket.send(json.dumps(event))
        logger.info("Agent interrupted")
    
    async def _send_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        """
        Send tool/function result back to agent.
        """
        event = {
            "type": "tool_response",
            "tool_name": tool_name,
            "result": result
        }
        
        await self.websocket.send(json.dumps(event))
    
    async def execute_function(
        self, 
        function_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute function - delegated to business logic layer.
        """
        return {
            "status": "delegated",
            "function": function_name,
            "arguments": arguments
        }
    
    async def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update conversation context.
        """
        event = {
            "type": "context_update",
            "context": context
        }
        
        await self.websocket.send(json.dumps(event))
    
    def register_callback(self, event: str, callback) -> None:
        """Register event callback."""
        self.callbacks[event] = callback
    
    async def get_session_state(self) -> Dict[str, Any]:
        """Get current session state."""
        return {
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "agent_id": self.agent_id,
            "connected": self.is_connected,
            "conversation_length": len(self.conversation_history),
            "average_latency": sum(self.latency_metrics) / len(self.latency_metrics) if self.latency_metrics else 0
        }
    
    async def disconnect(self) -> None:
        """Close connection and cleanup."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            
        await self.http_client.aclose()
        
        logger.info("Disconnected from ElevenLabs")
    
    # Voice customization methods
    
    async def clone_voice(
        self, 
        name: str, 
        audio_samples: list[bytes],
        description: str = ""
    ) -> str:
        """
        Clone a custom voice for the business.
        
        Returns:
            voice_id: ID of the cloned voice
        """
        # ElevenLabs voice cloning
        files = [("files", sample) for sample in audio_samples]
        
        data = {
            "name": name,
            "description": description
        }
        
        response = await self.http_client.post(
            "/voices/add",
            files=files,
            data=data
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Voice cloning failed: {response.text}")
        
        voice_data = response.json()
        voice_id = voice_data["voice_id"]
        
        logger.info(f"Voice cloned successfully: {voice_id}")
        return voice_id
    
    async def list_voices(self) -> list[Dict[str, Any]]:
        """
        List all available voices.
        """
        response = await self.http_client.get("/voices")
        data = response.json()
        return data.get("voices", [])
