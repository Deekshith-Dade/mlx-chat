from dataclasses import dataclass
import platform
import subprocess

from textual import containers, on
from textual.message import Message
from textual.widgets import Button, Markdown
from textual.widgets.markdown import MarkdownStream


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard with platform-specific handling.
    
    Returns True if successful, False otherwise.
    """
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0
        elif system == "Linux":
            # Try xclip first, then xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, close_fds=True)
                    process.communicate(input=text.encode("utf-8"))
                    if process.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
            return False
        elif system == "Windows":
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(input=text.encode("utf-16-le"))
            return process.returncode == 0
        return False
    except Exception:
        return False


@dataclass
class STTResponseUpdate(Message):
    text: str


class CopyButton(Button):
    """A button that copies text and shows feedback."""
    
    def __init__(self) -> None:
        super().__init__("📋", id="copy-btn")
        self._original_label = "📋"
    
    def show_copied(self) -> None:
        """Show copied feedback, then revert after a delay."""
        self.label = "✓"
        self.add_class("-copied")
        self.remove_class("-failed")
        self.set_timer(1.5, self._reset_label)
    
    def show_failed(self) -> None:
        """Show failed feedback, then revert after a delay."""
        self.label = "✗"
        self.add_class("-failed")
        self.remove_class("-copied")
        self.set_timer(1.5, self._reset_label)
    
    def _reset_label(self) -> None:
        self.label = self._original_label
        self.remove_class("-copied")
        self.remove_class("-failed")


class STTResponse(containers.Vertical):
    """A response container with markdown content and a copy button."""
    
    BORDER_TITLE = "Le Chat"

    DEFAULT_CSS = """
    STTResponse {
        height: auto;
        
        #header {
            height: 1;
            width: 100%;
            background: transparent;
        }
        
        #content {
            height: auto;
            width: 100%;
            padding: 0;
        }
    }
    """

    def __init__(self, markdown: str | None = None) -> None:
        super().__init__()
        self._initial_markdown = markdown
        self._stream: MarkdownStream | None = None
        self._full_text: str = markdown or ""
    
    def compose(self):
        with containers.Horizontal(id="header"):
            yield CopyButton()
        yield Markdown(self._initial_markdown, id="content")
    
    @property
    def markdown_widget(self) -> Markdown:
        return self.query_one("#content", Markdown)
    
    @property
    def stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = Markdown.get_stream(self.markdown_widget)
        return self._stream

    async def append_fragment(self, fragment: str) -> None:
        self._full_text += fragment
        await self.stream.write(fragment)
    
    @property
    def text(self) -> str:
        """Get the full transcription text."""
        return self._full_text
    
    @on(Button.Pressed, "#copy-btn")
    def on_copy_pressed(self, event: Button.Pressed) -> None:
        """Copy the transcription text to clipboard."""
        event.stop()
        copy_btn = self.query_one("#copy-btn", CopyButton)
        if copy_to_clipboard(self._full_text):
            copy_btn.show_copied()
        else:
            copy_btn.show_failed()