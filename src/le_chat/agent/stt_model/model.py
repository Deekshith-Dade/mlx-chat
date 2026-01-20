
import queue
import threading
from typing import Union
from pathlib import Path

import mlx.core as mx
# Import huggingface_utils first to apply tqdm patches before other imports
from le_chat.agent.huggingface_utils import download_model

from textual.message_pump import MessagePump
from le_chat.agent.stt_model.base import STTModelBase, STTModelFail, STTModelReady, STTModelLoading, STTFullTranscriptionReady
from le_chat.agent.stt_model.utils import extract_audio_paths
from mlx_audio.utils import load_model

from le_chat.widgets.stt_response import STTResponseUpdate

generation_stream = mx.new_stream(mx.default_device())

class MLXAudioSTTModel(STTModelBase):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        self.model = None
        self._cancel_event: threading.Event = threading.Event()
        self._is_generating: bool = False
        self._process_queue = queue.Queue(maxsize=10)
    
    def _update_loading_status(self, status: str) -> None:
        self.post_message(STTModelLoading(status))

    def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        try:
            self.model = load_model(self.model_name)
            self.post_message(STTModelReady())
        except Exception:
            self._update_loading_status(f"Downloading {self.model_name}...")
            try:
                if download_model(self.model_name, self._update_loading_status):
                    self._update_loading_status(f"Loading {self.model_name}...")
                    self.model = load_model(self.model_name)
                    self.post_message(STTModelReady())
                else:
                    self.post_message(STTModelFail("Download Failed", f"Failed to download model {self.model_name}."))
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                self.post_message(STTModelFail(str(e), "Loading Failed"))
    
    # async def change_model
    async def submit_prompt(self, prompt: str) -> None:
        """Extract audio files from the prompt and transcribe them."""
        audio_paths = extract_audio_paths(prompt)
        if not audio_paths:
            self.post_message(STTModelFail("No audio files found", "No audio files in prompt"))
            return
        await self.transcribe_audio(audio_paths)
        self.post_message(STTFullTranscriptionReady())

    async def transcribe_audio(self, audio_path: Union[str, list[str]]) -> None:
        """Transcribe a single audio file or a list of audio files."""
        if self.model is None:
            self.post_message(STTModelFail("Model not loaded", "Model not loaded"))
            return
        if isinstance(audio_path, str):
            audio_path = [audio_path]
        for idx, path in enumerate(audio_path):
            try:
                segments = self.model.generate(path, generation_stream=generation_stream, verbose=True)
                if idx > 0:
                    self.post_message(STTResponseUpdate("\n\n---\n\n"))
                filename = Path(path).name
                self.post_message(STTResponseUpdate(f"**{filename}**\n\n"))
                self.post_message(STTResponseUpdate(segments.text))
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                self.post_message(STTModelFail(str(e), f"Failed to transcribe {path}"))

    async def transcribe(self) -> None:
        self._cancel_event.clear()
        while not self._cancel_event.is_set():
            try:
                audio_path = self._process_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Sentinel value signals end of input
            if audio_path is None:
                break

            self._is_generating = True
            try:
                segments = self.model.generate(audio_path, verbose=True)
                transcription = segments.text
                self.post_message(STTResponseUpdate(transcription))
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                self.post_message(STTModelFail(str(e), "Transcription Failed"))
            finally:
                self._is_generating = False
        
        self._is_generating = False
        self.post_message(STTFullTranscriptionReady())
                

    async def insert_audio(self, audio_path: str) -> None:
        try:
            self._process_queue.put(audio_path)
        except queue.Full:
            self._process_queue.get()
            try:
                self._process_queue.put(audio_path)
            except queue.Full:
                pass
        
    async def finish(self) -> None:
        """Signal that no more audio will be added."""
        self._process_queue.put(None)

    async def cancel(self) -> bool:
        if not self._cancel_event.is_set():
            self._cancel_event.set()
            return True
        return False
            