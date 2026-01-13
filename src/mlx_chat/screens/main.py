from dataclasses import dataclass
from typing import Any, Optional
import llm
from textual import on, work
from textual import containers
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from mlx_chat.agent.agent import AgentReady
from mlx_chat.widgets.conversation import Conversation



class MainScreen(Screen):
    CSS_PATH = "main.tcss"

    # def __init__(self, model: Optional[Any] = None):
    #     super().__init__()
    
    def compose(self) -> ComposeResult:
        with containers.Center():
            yield Conversation()
        yield Footer()
    
       
