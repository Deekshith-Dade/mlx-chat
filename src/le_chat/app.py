from typing import TYPE_CHECKING, ClassVar, Optional

from textual import on, work
from textual.app import App 
from textual.binding import Binding, BindingType
from textual.reactive import var

from le_chat.agent.agent import AgentFail, AgentLoading, AgentReady
from le_chat.agent.stt_model.base import STTModelFail, STTModelLoading, STTModelReady

from le_chat.screens.loading import LoadingScreen

if TYPE_CHECKING:
    from le_chat.screens.chat import ChatScreen
    from le_chat.screens.settings import SettingsScreen
    from le_chat.screens.launcher import Launcher
    from le_chat.screens.stt import SttScreen
    
SYSTEM = """Formulate all responses as if you where the sentient AI named Mother from the Aliens movies."""

def get_settings_screen() -> "SettingsScreen":
    from le_chat.screens.settings import SettingsScreen

    return SettingsScreen()

def get_loading_screen() -> "LoadingScreen":

    return LoadingScreen()

def get_chat_screen() -> "ChatScreen":
        from le_chat.screens.chat import ChatScreen

        return ChatScreen()

def get_launcher_screen() -> "Launcher":
        from le_chat.screens.launcher import LauncherScreen
        
        return LauncherScreen()

def get_stt_screen() -> "SttScreen":
    from le_chat.screens.stt import SttScreen

    return SttScreen()

class ChatApp(App):

    SCREENS = {
        "settings": get_settings_screen,
        "loading": get_loading_screen,
        "chat": get_chat_screen,
    }

    MODES = {
        "launcher": get_launcher_screen,
        "chat": get_chat_screen,
        "stt": get_stt_screen,
    }


    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(
            "f1",
            "settings",
            "Settings",
            tooltip="Settings screen"
        ),
        Binding(
            "f2",
            "switch_mode('chat')",
            "Chat Mode",
            tooltip="Switch to Chat Mode"
        ),
        Binding(
            "f3",
            "switch_mode('stt')",
            "STT Mode",
            tooltip="Switch to STT Mode"
        ),
    ]
    
    loading_screen: LoadingScreen | None = None
    _settings = var(dict) # should have interactionitems
    def __init__(self, mode: Optional[str] = None):
        self._initial_mode = mode
        super().__init__()

    def on_mount(self) -> None:
        if mode := self._initial_mode:
            self.switch_mode(mode)
        else:
            self.switch_mode("chat")

    @work
    async def action_settings(self) -> None:
        await self.push_screen_wait("settings")
    
    @on(AgentLoading)
    async def on_agent_loading(self, event: AgentLoading) -> None:
        if self.loading_screen is not None:
            self.loading_screen.loading_text = event.loading_message
        else:
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

    @on(STTModelLoading)
    async def on_stt_model_loading(self, event: STTModelLoading) -> None:
        if self.loading_screen is not None:
            self.loading_screen.loading_text = event.loading_message
        else:
            self.loading_screen = self.get_screen("loading")
            self.loading_screen.loading_text = event.loading_message
            await self.push_screen(self.loading_screen)

    @on(STTModelReady)
    async def on_stt_model_ready(self, event: STTModelReady) -> None:
        if self.loading_screen is not None:
            await self.loading_screen.action_dismiss()

    @on(STTModelFail)
    async def on_stt_model_fail(self, event: STTModelFail) -> None:
        if self.loading_screen is not None:
            await self.loading_screen.action_dismiss()
            self.loading_screen = None
       
