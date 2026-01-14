from dataclasses import dataclass
from typing import Optional
from textual.reactive import reactive, var
from textual.message import Message
from textual.widgets import Markdown
from textual.widgets.markdown import MarkdownStream


@dataclass
class ResponseUpdate(Message):
    text: str

@dataclass
class ResponseMetadataUpdate(Message):
    prompt_tokens: Optional[int] = None
    generation_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    prompt_tps: Optional[float] = None
    generation_tps: Optional[float] = None
    peak_memory: Optional[float] = None
    

class Response(Markdown):
    BORDER_TITLE = "Le Chat"
    show_response_metadata = var(True)

    def __init__(self, markdown: str | None = None) -> None:
        super().__init__(markdown)
        self._stream: MarkdownStream | None = None
        self._metadata: ResponseMetadataUpdate | None = None

    @property
    def stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = self.get_stream(self)
        return self._stream
    
    async def append_fragment(self, fragment: str) -> None:
        await self.stream.write(fragment)
    
    async def update_border_subtitle(self, details: ResponseMetadataUpdate) -> None:
        self._metadata = details
        if self.show_response_metadata:
            tps_strs = []
            if details.prompt_tps is not None:
                tps_strs.append(f"prompt TPS: {details.prompt_tps:.2f}")
            if details.generation_tps is not None:
                tps_strs.append(f"gen TPS: {details.generation_tps:.2f}")
            tps_info = ", ".join(tps_strs) if tps_strs else ""
            mem_info = f"Peak Mem: {details.peak_memory:.2f} GB" if details.peak_memory is not None else ""
            info = " | ".join(filter(None, [tps_info, mem_info]))
            self.border_subtitle = info or " "
        else:
            self.border_subtitle = ""
        