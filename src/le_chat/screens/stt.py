from textual import containers, on, work, events
from textual.reactive import var
from textual.screen import Screen

from le_chat.agent.stt_model.base import STTFullTranscriptionReady, STTModelLoading, STTModelReady
from le_chat.audio import AudioProcessor
from le_chat.widgets.stt_response import STTResponse, STTResponseUpdate
from le_chat.widgets.non_selectable_label import NonSelectableLabel
from le_chat.widgets.throbber import Throbber




class SttScreen(Screen):
    CSS_PATH = "stt.tcss"

    BINDINGS = [
        ("escape", "cancel_generation", "Stop Recording"),
    ]

    model_name: var[str | None] = var("mlx-community/whisper-large-v3-turbo")

    def __init__(self, sample_rate=16000, chunk_sec=5.0):
        super().__init__()
        self.sample_rate = sample_rate
        self.chunk_sec = chunk_sec
        self.audio_processor = AudioProcessor(chunk_sec=self.chunk_sec, sample_rate=self.sample_rate)
        self._recording: bool = False
        self._model_response: STTResponse | None = None

    async def on_mount(self) -> None:
        self.post_message(STTModelLoading(loading_message="Loading STT Model..."))
        # Start the STT model load immediately after mount.
        self.load_model()

    @work(thread=True)
    def load_model(self) -> None:
        from le_chat.agent.stt_model import MLXAudioSTTModel as STTModel
        self.audio_model = STTModel(self.model_name)
        print("Starting STT model...")
        self.audio_model.start(self)

    @work(thread=True)
    async def run_transcriber(self) -> None:
        # Continuously consume audio paths from the model queue and emit STTResponseUpdate messages.
        await self.audio_model.transcribe()

    def compose(self):
        yield Throbber(id="throbber")
        with containers.Vertical(id="stt-layout"):
            yield NonSelectableLabel("Idle", id="recording-indicator")
            yield containers.Vertical(id="stt-view")

    async def on_key(self, event: events.Key) -> None:
        """Toggle recording on each space press."""
        if event.key != "space":
            return
        event.stop()
        if not self._recording:
            self._recording = True
            self.audio_processor.start()
            self._start_chunk_producer()
            self._set_recording_indicator(recording=True)
            self.run_transcriber()
        else:
            self._recording = False
            # Stop processor but flush the partial buffer so remaining audio becomes a final chunk.
            self.audio_processor.stop(flush_partial=True)
            self._set_recording_indicator(recording=False)

    def _start_chunk_producer(self) -> None:
        self._produce_chunks()

    @work(thread=True)
    async def _produce_chunks(self) -> None:
        for chunk_path in self.audio_processor.chunk_and_save_wav(output_path="output.wav"):
            print(chunk_path)
            await self.audio_model.insert_audio(str(chunk_path))
        await self.audio_model.finish()

    def _set_recording_indicator(self, recording: bool) -> None:
        indicator = self.query_one("#recording-indicator", NonSelectableLabel)
        indicator.update("Recording..." if recording else "Idle")
        indicator.set_class(recording, "-recording")

    @on(STTResponseUpdate)
    async def on_STTResponseUpdate(self, message: STTResponseUpdate) -> None:
        """Update the UI when the STT model produces new text."""
        if not message.text:
            return
        if self._model_response is None:
            stt_view = self.query_one("#stt-view", containers.Vertical)
            self._model_response = STTResponse()
            self._model_response.border_title = self.model_name.upper()
            await stt_view.mount(self._model_response)
        stt_response = self._model_response
        await stt_response.append_fragment(message.text + " ")

    @on(STTFullTranscriptionReady)
    async def on_STTFullTranscriptionReady(self, message: STTFullTranscriptionReady) -> None:
        """Handle end of full transcription."""
        self._model_response = None
        self.audio_model.cancel()
    
    async def action_stop_generation(self) -> None:
        """Action to stop recording."""
        if self._recording:
            self._recording = False
            self.audio_processor.stop(flush_partial=True)
            self._set_recording_indicator(recording=False)
            self.audio_model.cancel()
            self._model_response = None
    