from textual import containers
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from le_chat.widgets.conversation import Conversation

class ChatScreen(Screen):
    CSS_PATH = "chat.tcss"

    # def __init__(self, model: Optional[Any] = None):
    #     super().__init__()
    
    def compose(self) -> ComposeResult:
        yield Conversation()
        yield Footer()