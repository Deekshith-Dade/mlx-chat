from dataclasses import dataclass
from textual import containers, lazy, on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, ScreenResultType
from textual.widgets import Footer, Input, Placeholder, Static, Switch

from le_chat.app import ChatApp

class SettingsScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Dismiss Settings"),
    ]

    CSS_PATH = "settings.tcss"

    # app = getters.app(ChatApp)

    # chat settings
    def __init__(self):
        super().__init__()
    
    def compose(self) -> ComposeResult:
        with containers.Vertical(id="contents"):
            with containers.VerticalGroup(classes="search-container"):
                yield Input(id="search", placeholder="Search settings")
            with lazy.Reveal(
                containers.VerticalScroll(can_focus=False, id="settings-container")
            ):
                yield Static("This will be Settings Menu")
                yield containers.Horizontal(
                    Static("off:     ", classes="label"),
                    Switch(value=self.show_response_info, id="response-info-switch"),
                    classes="container",
                )
        yield Footer()
    
    async def action_dismiss(self, result: ScreenResultType | None = None) -> None:
        # return await super().action_dismiss(result)
        self.call_after_refresh(self.dismiss, result)
