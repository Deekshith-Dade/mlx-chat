from textual import containers
from textual.app import ComposeResult
from textual.widgets import Input


class Prompt(containers.VerticalGroup):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Type Message here....", id="input-area")
        