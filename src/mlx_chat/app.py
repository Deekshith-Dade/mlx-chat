from typing import TYPE_CHECKING, ClassVar, Optional

from textual import getters, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Header, Input, Footer, Markdown
from textual.containers import VerticalScroll
import llm

from mlx_chat.agent.agent import AgentFail, AgentLoading, AgentReady

from mlx_chat.screens.loading import LoadingScreen

if TYPE_CHECKING:
    from mlx_chat.screens.main import MainScreen
    from mlx_chat.screens.settings import SettingsScreen
    
SYSTEM = """Formulate all responses as if you where the sentient AI named Mother from the Aliens movies."""

def get_settings_screen() -> "SettingsScreen":
    from mlx_chat.screens.settings import SettingsScreen

    return SettingsScreen()

def get_loading_screen() -> "LoadingScreen":

    return LoadingScreen()

class ChatApp(App):
    # bindings and stuff
    # AUTO_FOCUS = "Input"

    SCREENS = {
        "settings": get_settings_screen,
        "loading": get_loading_screen,
    }

    MODES = {}
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(
            "f2,ctrl+comma",
            "settings",
            "Settings",
            tooltip="Settings screen"
        )
    ]
    
    loading_screen: LoadingScreen | None = None
    # def __init__(self, config):
        # self.config = config

    def on_mount(self) -> None:
        self.push_screen(self.get_main_screen())

    def get_main_screen(self) -> "MainScreen":
        from mlx_chat.screens.main import MainScreen

        return MainScreen()

    @work
    async def action_settings(self) -> None:
        await self.push_screen_wait("settings")
    
    @on(AgentLoading)
    async def on_agent_loading(self, event: AgentLoading) -> None:
        self.loading_screen = self.get_screen("loading")
        self.loading_screen.loading_text = event.loading_message
        await self.push_screen(self.loading_screen)

    @on(AgentReady)
    async def on_agent_ready(self, event: AgentReady) -> None:
        if self.loading_screen is not None:
            await self.loading_screen.action_dismiss()

    @on(AgentFail)
    async def on_agent_fail(self, event: AgentFail) -> None:
        if self.loading_screen is not None:
            await self.loading_screen.action_dismiss()
            self.loading_screen = None
        
 

       
if __name__ == "__main__":
    app = ChatApp()
    app.run()