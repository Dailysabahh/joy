"""
Base Engine Interface for Closer Assistant

All conversation engines (OpenAI Realtime, ElevenLabs, etc.) 
must implement this interface to ensure consistency across the platform.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class EngineType(Enum):
    OPENAI_REALTIME = "openai_realtime"
    ELEVENLABS_AGENT = "elevenlabs_agent"
    GEMINI_LIVE = "gemini_live"


class TurnType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"


@dataclass
class AudioChunk:
    """Audio data chunk for streaming"""
    data: bytes
    sample_rate: int = 24000
    channels: int = 1
    format: str = "pcm16"  # or "g711_ulaw" for telephony


@dataclass
class ConversationTurn:
    """A single turn in the conversation"""
    type: TurnType
    content: Optional[str] = None
    audio: Optional[bytes] = None
    function_name: Optional[str] = None
    function_args: Optional[Dict[str, Any]] = None
    function_result: Optional[Any] = None
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SessionConfig:
    """Configuration for a conversation session"""
    worker_id: str
    business_id: str
    channel: str  # "phone", "web", "chat"
    language: str = "en"
    voice_id: Optional[str] = None
    personality: Optional[Dict[str, Any]] = None
    knowledge_base: Optional[Dict[str, Any]] = None
    available_functions: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None


class BaseEngine(ABC):
    """
    Abstract base class for all conversation engines.
    
    Ensures that OpenAI Realtime, ElevenLabs, and any future engines
    have a consistent interface for the Closer Assistant platform.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session_id: Optional[str] = None
        self.is_connected: bool = False
        self.callbacks: Dict[str, Callable] = {}
        
    @abstractmethod
    async def connect(self, session_config: SessionConfig) -> str:
        """
        Establish connection to the engine and start a session.
        
        Returns:
            session_id: Unique identifier for this conversation session
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection and clean up resources."""
        pass
    
    @abstractmethod
    async def send_audio(self, audio_chunk: AudioChunk) -> None:
        """
        Stream audio input to the engine.
        
        Args:
            audio_chunk: Audio data from user (phone, mic, etc.)
        """
        pass
    
    @abstractmethod
    async def send_text(self, text: str) -> None:
        """
        Send text input to the engine (for chat channels).
        
        Args:
            text: User's text message
        """
        pass
    
    @abstractmethod
    async def interrupt(self) -> None:
        """
        Interrupt the current assistant response immediately.
        Critical for natural conversation flow.
        """
        pass
    
    @abstractmethod
    async def execute_function(
        self, 
        function_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a function call requested by the AI.
        
        Args:
            function_name: Name of the function to call
            arguments: Function arguments
            
        Returns:
            Function result to send back to the AI
        """
        pass
    
    @abstractmethod
    async def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update the conversation context dynamically.
        
        Args:
            context: New or updated context (business info, memory, etc.)
        """
        pass
    
    @abstractmethod
    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register callbacks for engine events.
        
        Events:
            - "audio_output": Fired when assistant speaks
            - "text_output": Transcript of what assistant said
            - "function_call": When AI wants to call a function
            - "turn_complete": When a conversation turn ends
            - "error": When an error occurs
            - "latency": Performance metrics
        """
        pass
    
    @abstractmethod
    async def get_session_state(self) -> Dict[str, Any]:
        """
        Get current session state for monitoring/debugging.
        
        Returns:
            Session state including turns, latency, costs, etc.
        """
        pass
    
    @property
    @abstractmethod
    def supports_realtime_audio(self) -> bool:
        """Whether this engine supports direct audio streaming."""
        pass
    
    @property
    @abstractmethod
    def supports_interruptions(self) -> bool:
        """Whether this engine handles interruptions naturally."""
        pass
    
    @property
    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Whether this engine can call functions/tools."""
        pass
    
    @property
    @abstractmethod
    def engine_type(self) -> EngineType:
        """Type of this engine."""
        pass
    
    # Helper methods (implemented in base class)
    
    def _emit_event(self, event: str, data: Any) -> None:
        """Emit an event to registered callbacks."""
        if event in self.callbacks:
            try:
                self.callbacks[event](data)
            except Exception as e:
                print(f"Error in callback for {event}: {e}")
    
    def _validate_session_config(self, config: SessionConfig) -> None:
        """Validate session configuration."""
        if not config.worker_id:
            raise ValueError("worker_id is required")
        if not config.business_id:
            raise ValueError("business_id is required")
        if not config.channel:
            raise ValueError("channel is required")
