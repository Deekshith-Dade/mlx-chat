from contextlib import suppress
from dataclasses import dataclass
from itertools import zip_longest
from tkinter import N
from typing import Literal, Self
from textual import containers, events, getters, on, work
from textual import widgets
from textual.app import ComposeResult
from textual.binding import Binding
from textual.content import Content
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder, Static

from mlx_chat import interaction_item_schema
from mlx_chat.app import ChatApp
from mlx_chat.interaction_item_schema import InteractionItemSchema
from mlx_chat.widgets import grid_select
from mlx_chat.widgets.grid_select import GridSelect 

@dataclass
class LaunchItem(Message):
    item_name: str

class LauncherGridSelect(GridSelect):
    
    HELP = """\
        Select the kind of interaction you would like with the models
    """

    BINDING_GROUP_TITLE = "Launcher"
    BINDINGS = [
        Binding(
            "enter",
            "select",
            "Details",
            tooltip="Open Interaction Details"
        ),
        Binding(
            "space",
            "launch",
            "Launch",
            tooltip="Launch highlighted Interaction"
        ),
    ]

    def action_details(self) -> None:
        if self.highlighted is None:
            return
        
        interaction_item = self.children[self.highlighted]
        assert isinstance(interaction_item, LauncherItem)
        self.post_message(LauncherScreen.OpenInteractionDetails[interaction_item]._interaction_items['item_name'])
    
    # def action_remove(self) -> None:

    def action_launch(self) -> None:
        if self.highlighted is None:
            return
        child = self.children[self.highlighted]
        assert isinstance(child, LauncherItem)
        self.post_message(LaunchItem(child._schema["item_name"]))

class Launcher(containers.VerticalGroup):
    app = getters.app(ChatApp)
    grid_select = getters.query_one("#launcher-grid-select", GridSelect)
    DIGITS = "123456789"

    def __init__(
        self,
        interaction_items: dict[str, InteractionItemSchema],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None
    ) -> None:
        self._interaction_items = interaction_items
        super().__init__(name=name, id=id, classes=classes)
    
    @property
    def highlighted(self) -> int | None:
        return self.grid_select.highlighted
    
    @highlighted.setter
    def highlighted(self, value: int) -> None:
        self.grid_select.highlighted = value
    
    def focus(self, scroll_visible: bool = True) -> Self:
        try:
            self.grid_select.focus(scroll_visible=scroll_visible)
        except NoMatches:
            pass
        return self
    
    def compose(self) -> ComposeResult:
        launcher_interaction_items = [*self._interaction_items] # TODO: get launcher_interaction_items from the settings
        if launcher_interaction_items:
            with LauncherGridSelect(
                id="launcher-grid-select", min_column_width=32, max_column_width=32
            ):
                for digit, interaction_item in zip_longest(self.DIGITS, launcher_interaction_items):
                    if interaction_item is None:
                        break
                    yield LauncherItem(digit or "", self._interaction_items[interaction_item])
        
        # if not launcher_interaction_items:
            # yield widgets.Label("Choose your")
    
class LauncherItem(containers.VerticalGroup):
    def __init__(self, digit: str, interaction_item: InteractionItemSchema) -> None:
        self._digit = digit 
        self._schema = interaction_item
        super().__init__()
    
    @property
    def schema(self) -> InteractionItemSchema:
        return self._schema
    
    def compose(self) -> ComposeResult:
        schema = self._schema
        with containers.HorizontalGroup():
            if self._digit:
                yield widgets.Digits(self._digit)
        with containers.VerticalGroup():
            yield widgets.Label(schema["display_name"], id="name")
            yield widgets.Label(schema["description"], id="description")

class Container(containers.VerticalScroll):
    BINDING_GROUP_TITLE = "View"

    def allow_focus(self) -> bool:
        """Only allow focus when we can scroll."""
        return super().allow_focus() and self.show_vertical_scrollbar
    
class LauncherScreen(Screen):
    BINDING_GROUP_TITLE = "Screen"
    CSS_PATH = "launcher.tcss"
    FOCUS_GROUP = Binding.Group("Focus")
    BINDINGS = [
        Binding(
            "tab",
            "app.focus_next",
            "Focus Next",
            group=FOCUS_GROUP,
        ),
        Binding(
            "shift+tab",
            "app.focus_previous",
            "Focus Previous",
            group=FOCUS_GROUP,
        ),
        Binding(
            "null",
            "quick_launch",
            "Quick launch",
            key_display="1-9 a-f",
        ),
    ]

    launcher = getters.query_one("#launcher", Launcher)
    container = getters.query_one("#container", Container)

    app = getters.app(ChatApp)

    @dataclass
    class OpenInteractionDetails(Message):
        item_name: str
    
    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        self._interaction_items: dict[str, InteractionItemSchema] = {}
        super().__init__(name=name, id=id, classes=classes)
    
    @property
    def interaction_items(self) -> dict[str, InteractionItemSchema]:
        return self._interaction_items
    
    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="title-container"):
            with containers.Grid(id="title-grid"):
                yield Static(content="Some Label")
                yield widgets.Label(self.get_info(), id="info")
    
        yield Container(id="container", can_focus=False)
        yield widgets.Footer()
    
    def get_info(self) -> Content:
        content = Content.from_markup("Le Chat")
        return content
    
    def move_focus(self, direction: Literal[-1] | Literal[+1]) -> None:
        if isinstance(self.focused, GridSelect):
            focus_chain = list(self.query(GridSelect))
            if self.focused in focus_chain:
                index = focus_chain.index(self.focused)
                new_focus = focus_chain[(index + direction) % len(focus_chain)]
                if direction == -1:
                    new_focus.highlight_last()
                else:
                    new_focus.highlight_first()
                new_focus.focus(scroll_visible=False)

    @on(GridSelect.LeaveUp)
    def on_grid_select_leave_up(self, event: GridSelect.LeaveUp):
        event.stop()
        self.move_focus(-1)
    
    @on(GridSelect.LeaveDown)
    def on_grid_select_leave_up(self, event: GridSelect.LeaveDown):
        event.stop()
        self.move_focus(+1)

    @on(GridSelect.Selected)
    @work
    async def on_grid_select_selected(self, event: GridSelect.Selected):
        assert isinstance(event.selected_widget, LauncherItem)
        # open any model to display information here
        from mlx_chat.screens.interaction_demo import InteractionDemo

        modal_response = await self.app.push_screen_wait(
            InteractionDemo(event.selected_widget.schema)
        )
        # self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchItem(event.selected_widget.schema["item_name"]))
    
    @on(OpenInteractionDetails)
    @work
    async def open_interaction_detail(self, message: OpenInteractionDetails) -> None:
        pass
        # open interaction modal  and post_message
        from mlx_chat.screens.interaction_demo import InteractionDemo

        try:
            interaction_schema = self._interaction_items[message.item_name]
        except KeyError:
            return
        modal_response = await self.app.push_screen_wait(InteractionDemo(interaction_schema))
        # self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchItem(interaction_schema["item_name"]))
    
    @on(GridSelect.Selected, "#launcher GridSelect")
    @work
    async def on_launcher_selected(self, event: GridSelect.Selected):
        launcher_item = event.selected_widget
        assert isinstance(launcher_item, LauncherItem)
        from mlx_chat.screens.interaction_demo import InteractionDemo

        modal_response = await self.app.push_screen_wait(
            InteractionDemo(event.selected_widget.schema)
        )
        # self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchItem(event.selected_widget.agent["item_name"]))

    @work
    async def launch_interaction(self, item_name: str) -> None:
        from mlx_chat.screens.main import MainScreen

        screen = None
        if item_name == "chat":
            screen = MainScreen()
        
        if screen is not None:
            await self.app.push_screen_wait(screen)
        
    @on(LaunchItem)
    def on_launch_item(self, message: LaunchItem) -> None:
        self.launch_interaction(message.item_name)
    
    def compose_interaction_items(self) -> ComposeResult:
        items = self._interaction_items

        yield Launcher(items, id="launcher")

    @work
    async def on_mount(self) -> None:
        data = {
            "chatapp" : InteractionItemSchema(item_name="chat", display_name="Chat with VLMs", description="Do whatever you want with OMNI Models"),
            "tts" : InteractionItemSchema(item_name="tts", display_name="Text To Speech Models", description="Do whatever you want with TTS Models"),
        }
        try:
            self._interaction_items = data
        except Exception as e:
            self.notify(
                f"Failed to read interaction data ({e})",
                title="Inteaction Items Data",
                severity="error"
            )
        else:
            await self.container.mount_compose(self.compose_interaction_items())
            with suppress(NoMatches):
                first_grid = self.container.query(GridSelect).first()
                first_grid.focus(scroll_visible=False)
    
    
    def on_key(self, event: events.Key) -> None:
        if event.character is None:
            return
        LAUNCHER_KEYS = "123456789abcdef"
        if event.character in LAUNCHER_KEYS:
            launch_item_offset = LAUNCHER_KEYS.find(event.character)
            try:
                self.launcher.grid_select.children[launch_item_offset]
            except IndexError:
                self.notify(
                    f"No agent on key [b]{LAUNCHER_KEYS[launch_item_offset]}",
                    title="Quick launch",
                    severity="error",
                )
                self.app.bell()
                return
            self.launcher.focus()
            self.launcher.highlighted = launch_item_offset
    
    def action_quick_launch(self) -> None:
        self.launcher.focus()

if __name__ == "__main__":
    from mlx_chat.app import ChatApp
    app = ChatApp(mode="launcher")
    app.run()