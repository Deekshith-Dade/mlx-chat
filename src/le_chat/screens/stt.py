from textual import containers, work, events
from textual.screen import Screen

from le_chat.agent.stt_model.base import STTModelLoading, STTModelReady
from le_chat.audio import AudioProcessor
from le_chat.widgets.stt_response import STTResponse, STTResponseUpdate
from le_chat.widgets.non_selectable_label import NonSelectableLabel
from le_chat.widgets.throbber import Throbber




class SttScreen(Screen):
    CSS_PATH = "stt.tcss"

    def __init__(self, sample_rate=16000, chunk_sec=5.0):
        super().__init__()
        self.sample_rate = sample_rate
        self.chunk_sec = chunk_sec
        self.audio_processor = AudioProcessor(chunk_sec=self.chunk_sec, sample_rate=self.sample_rate)
        self._recording: bool = False

    async def on_mount(self) -> None:
        self.post_message(STTModelLoading(loading_message="Loading STT Model..."))
        # Start the STT model load immediately after mount.
        self.load_model()

    @work(thread=True)
    def load_model(self) -> None:
        from le_chat.agent.stt_model import MLXAudioSTTModel as STTModel
        self.audio_model = STTModel("mlx-community/whisper-large-v3-turbo")
        print("Starting STT model...")
        self.audio_model.start(self)
        self.run_transcriber()

    @work(thread=True)
    async def run_transcriber(self) -> None:
        # Continuously consume audio paths from the model queue and emit STTResponseUpdate messages.
        await self.audio_model.transcribe()

    def compose(self):
        yield Throbber(id="throbber")
        with containers.Vertical(id="stt-layout"):
            yield NonSelectableLabel("Idle", id="recording-indicator")
            yield containers.Vertical(id="stt-view")
            yield STTResponse()

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
        else:
            self._recording = False
            # Stop processor but flush the partial buffer so remaining audio becomes a final chunk.
            self.audio_processor.stop(flush_partial=True)
            self._set_recording_indicator(recording=False)

    def _start_chunk_producer(self) -> None:
        # Run chunk production and enqueue paths to the STT model in a worker thread.
        self._produce_chunks()

    @work(thread=True)
    async def _produce_chunks(self) -> None:
        for chunk_path in self.audio_processor.chunk_and_save_wav(output_path="output.wav"):
            # Stop early if recording has been toggled off.
            # if not self._recording:
            #     break
            print(chunk_path)
            await self.audio_model.insert_audio(str(chunk_path))

    def _set_recording_indicator(self, recording: bool) -> None:
        indicator = self.query_one("#recording-indicator", NonSelectableLabel)
        indicator.update("Recording..." if recording else "Idle")
        indicator.set_class(recording, "-recording")

    async def on_STTResponseUpdate(self, message: STTResponseUpdate) -> None:
        """Update the UI when the STT model produces new text."""
        stt_response = self.query_one(STTResponse)
        await stt_response.append_fragment(message.text + " ")

    