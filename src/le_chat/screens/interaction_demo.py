
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Placeholder

from le_chat.interaction_item_schema import InteractionItemSchema


class InteractionDemo(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss(None)", "Dismiss", show=False),
        Binding("space", "dismiss('launch')", "Launch agent", priority=True),
    ]

    def __init__(self, schema: InteractionItemSchema):
        self._schema = schema

    def compose(self) -> ComposeResult:
        yield Placeholder(label="Interaction Demo Modal")
    
    def on_mount(self) -> None:
        self.query_one("#Footer").styles.animate("opacity", 1.0, duration = 500 / 1000)