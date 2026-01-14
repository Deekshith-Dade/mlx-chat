from typing import Iterable
from textual import containers
from textual.app import ComposeResult
from textual.widgets import Markdown

from le_chat.menus import MenuItem
from le_chat.widgets.non_selectable_label import NonSelectableLabel

class UserInput(Markdown):
    pass

class UserInput(containers.HorizontalGroup):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        yield NonSelectableLabel("❯", id="prompt")
        yield Markdown(self.content, id="content")

    def get_block_menu(self) -> Iterable[MenuItem]:
        yield from ()

    def get_block_content(self, destination: str) -> str | None:
        return self.content