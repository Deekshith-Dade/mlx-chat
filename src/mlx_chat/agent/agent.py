from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from textual.content import Content
from textual.message import Message
from textual.message_pump import MessagePump

class AgentReady(Message):
    """Agent is ready."""

@dataclass
class AgentFail(Message):
    """Agent Failed to Start"""
    message: str
    details: str = ""

@dataclass
class MessageDetails(ABC):
    """Contains Additional Message Info like TPS, PrefillTime, DecodeTime etc"""

@dataclass
class MessageContainer(ABC):
    role: str
    content: str
    details: Optional[MessageDetails] = None

class AgentBase(ABC):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._message_target: MessagePump | None = None
        self.history: list[MessageContainer] = []
        super().__init__()
    
    def post_message(self, message: Message) -> bool:
        if (message_target := self._message_target) is None:
            return False
        return message_target.post_message(message)

    @abstractmethod
    async def send_prompt(self, prompt: str) -> str | None:
        """"""
    
    async def cancel(self) -> bool:
        """"""

        return False
    
    async def change_model(self, model_name: str) -> bool | None:
        """Changes Model during the session"""
        self.model_name = model_name
        return False


    async def set_mode(self, mode_id: str) -> str | None:
        """Put the agent in a new mode."""
    
    def get_info(self) -> Content:
        return Content("")
    
    async def stop(self) -> None:
        "Stop the agent(gracefully exit the process)"
