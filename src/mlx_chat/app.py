from typing import TYPE_CHECKING, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Header, Input, Footer, Markdown
from textual.containers import VerticalScroll
import llm

if TYPE_CHECKING:
    from mlx_chat.screens.main import MainScreen
    from mlx_chat.screens.settings import SettingsScreen

SYSTEM = """Formulate all responses as if you where the sentient AI named Mother from the Aliens movies."""

def get_settings_screen() -> "SettingsScreen":
    from mlx_chat.screens.settings import SettingsScreen

    return SettingsScreen()

class ChatApp(App):
    # bindings and stuff
    # AUTO_FOCUS = "Input"

    SCREENS = {"settings": get_settings_screen}
    MODES = {}
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(
            "f2,ctrl+comma",
            "settings",
            "Settings",
            tooltip="Settings screen"
        )
    ]
    # def __init__(self, config):
        # self.config = config

    def on_mount(self) -> None:
        self.push_screen(self.get_main_screen())

    def get_main_screen(self) -> "MainScreen":
        from mlx_chat.screens.main import MainScreen

        return MainScreen(model="mlx-community/gemma-3n-E2B-it-4bit")

    @work
    async def action_settings(self) -> None:
        await self.push_screen_wait("settings")

       
if __name__ == "__main__":
    app = ChatApp()
    app.run()