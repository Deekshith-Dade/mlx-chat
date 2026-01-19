
import queue
import threading

from textual.message_pump import MessagePump
from le_chat.agent.huggingface_utils import download_model
from le_chat.agent.stt_model.base import STTModelBase, STTModelFail, STTModelReady, STTModelLoading

from mlx_audio.utils import load_model

from le_chat.widgets.stt_response import STTResponseUpdate


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
            print(self.model)
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
                self.post_message(STTModelFail(str(e), "Loading Failed"))
    
    # async def change_model

    async def transcribe(self) -> None:
        while not self._cancel_event.is_set():
            try:
                audio_path = self._process_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            self._is_generating = True
            try:
                segments = self.model.generate(audio_path)
                transcription = " ".join([segment.text for segment in segments])
                self.post_message(STTResponseUpdate(transcription))
            except Exception as e:
                self.post_message(STTModelFail(str(e), "Transcription Failed"))
            # finally:
            #     self._is_generating = False

    async def insert_audio(self, audio_path: str) -> None:
        try:
            self._process_queue.put(audio_path)
        except queue.Full:
            self._process_queue.get()
            try:
                self._process_queue.put(audio_path)
            except queue.Full:
                pass
        
    async def cancel(self) -> bool:
        if not self._cancel_event.is_set():
            self._cancel_event.set()
            return True
        return False
            