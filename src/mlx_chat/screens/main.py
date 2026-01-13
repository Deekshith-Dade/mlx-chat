from dataclasses import dataclass
from typing import Any, Optional
import llm
from textual import on, work
from textual import containers
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from mlx_chat.widgets.conversation import Conversation


class MainScreen(Screen):
    CSS_PATH = "main.tcss"

    def __init__(self, model: Optional[Any] = None):
        super().__init__()
        self.model_name = model
    
    def compose(self) -> ComposeResult:
        # yield Header()
        # with Vertical(id="chat-view"):
        #     yield Response("INTERFACE 2037 READY FOR INQUIRY")
        # yield Input(placeholder="How can I help you?")
        with containers.Center():
            yield Conversation(model_name=self.model_name)
        yield Footer()
