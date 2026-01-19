
from abc import ABC
from dataclasses import dataclass
from typing import Optional

from textual.message import Message
from textual.message_pump import MessagePump

class STTModelReady(Message):
    """STT Model ready."""

@dataclass
class STTModelLoading(Message):
    """Agent is being loaded."""
    loading_message: Optional[str] = None

@dataclass
class STTModelFail(Message):
    """Agent Failed to Start"""
    message: str
    details: str = ""


class STTModelBase(ABC):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._message_target : MessagePump | None = None
        super().__init__()
    
    def post_message(self, message: MessagePump) -> bool:
        if (message_target := self._message_target) is None:
            return False
        return message_target.post_message(message)
    