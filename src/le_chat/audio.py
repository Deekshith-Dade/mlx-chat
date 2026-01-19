from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import time
import wave
import numpy as np
import sounddevice as sd


@dataclass
class AudioChunk:
    seq: int
    t0: float
    t1: float
    samples: np.ndarray

class AudioProcessor:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_sec: float = 5.0,
        block_sec: float = 0.05,
        dtype: str = "float32",
        max_queue_chunks: int = 4,
        drop_oldest_on_overflow: bool = True,
    ) -> None:
        assert channels == 1, "Only mono audio is supported."
        self.sr = sample_rate
        self.channels = channels
        self.chunk_sec = chunk_sec
        self.block_sec = block_sec
        self.dtype = dtype
        
        self.chunk_samples = int(round(self.sr * self.chunk_sec))
        self.block_samples = int(round(self.sr * self.block_sec))

        self._stop = threading.Event()
        self._frames_q = queue.Queue(maxsize=max_queue_chunks * 50)
        self._chunks_q = queue.Queue(maxsize=max_queue_chunks)

        self._drop_oldest = drop_oldest_on_overflow
        self._worker = None
        self._stream = None
        self._flush_partial = False
    
    def start(self):
        self._stop.clear()
        self._worker = threading.Thread(target=self._chunker_loop, daemon=True)
        self._worker.start()

        def callback(indata, frames, time_info, status):
            if status:
                pass # Handle status if needed

            if self._stop.is_set():
                return
            x = indata[:, 0].copy()
            try:
                self._frames_q.put_nowait((time.monotonic(), x))
            except queue.Full:
                pass
        
        self._stream = sd.InputStream(
            samplerate=self.sr,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=self.block_samples,
            callback=callback,
        )

        self._stream.start()

    def stop(self, flush_partial: bool = False):
        self._stop.set()
        self._flush_partial = flush_partial
        if self._stream is not None:
            try:
                self._stream.stop()
            finally:
                self._stream.close()
            self._stream = None
        
        # chunker exit
        try:
            self._frames_q.put_nowait((None, None))
        except queue.Full:
            pass

        if self._worker is not None:
            self._worker.join(timeout=1.0)
            self._worker = None
        
        if not flush_partial:
            self._drain_queue(self._chunks_q)
        
        # end of stream marker for consumer
        try:
            self._chunks_q.put_nowait(None)
        except queue.Full:
            if self._drop_oldest:
                try:
                    self._chunks_q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._chunks_q.put_nowait(None)
                except queue.Full:
                    pass
    
    def chunks(self):
        while True:
            item = self._chunks_q.get()
            if item is None:
                return
            yield item

    def _chunker_loop(self):
        buf = np.empty((0,), dtype=np.float32)
        t0 = None
        seq = 0

        while True:
            ts, x = self._frames_q.get()
            if ts is None and x is None:
                break

            if t0 is None:
                t0 = ts
            
            if x.dtype != np.float32:
                x = x.astype(np.float32)
            
            buf = np.concatenate([buf, x], axis=0)

            while buf.shape[0] >= self.chunk_samples:
                chunk = buf[:self.chunk_samples]
                buf = buf[self.chunk_samples: ]
                t1 = t0 + (self.chunk_samples / self.sr)
                out = AudioChunk(seq=seq, t0=t0, t1=t1, samples=chunk)
                seq += 1
                t0 = t1

                self._put_chunk(out)

        if self._flush_partial and buf.shape[0] > 0:
            # Flush any remaining audio as a final partial chunk.
            t1 = t0 + (buf.shape[0] / self.sr) if t0 is not None else 0.0
            out = AudioChunk(seq=seq, t0=t0 or 0.0, t1=t1, samples=buf)
            self._put_chunk(out)

    def _put_chunk(self, chunk: AudioChunk):
        if not self._chunks_q.full():
            self._chunks_q.put_nowait(chunk)
            return
        
        if self._drop_oldest:
            try:
                self._chunks_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._chunks_q.put_nowait(chunk)
            except queue.Full:
                pass

    @staticmethod
    def _drain_queue(q: queue.Queue):
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            return

    @staticmethod
    def _write_wav(path: Path, samples: np.ndarray, sample_rate: int):
        """Persist mono float32 samples to a 16-bit PCM WAV."""
        path.parent.mkdir(parents=True, exist_ok=True)
        clipped = np.clip(samples, -1.0, 1.0)
        pcm16 = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm16.tobytes())

    def chunk_and_save_wav(self, output_path: str | Path):
        for chunk in self.chunks():
            chunk_path = Path(output_path).with_name(
                f"{Path(output_path).stem}_chunk{chunk.seq:04d}.wav"
            )
            self._write_wav(chunk_path, chunk.samples, self.sr)
            yield str(chunk_path.resolve())
        
    def record_wav(self, output_path: str | Path, duration_sec: float):
        """
        Record audio for the specified duration and save to a WAV file.

        The method starts the stream, collects chunks, trims to the exact
        duration, and writes a mono 16-bit PCM WAV.
        """
        self.start()
        deadline = time.monotonic() + duration_sec
        collected: list[np.ndarray] = []
        try:
            for chunk in self.chunks():
                collected.append(chunk.samples.copy())
                if chunk.t1 >= deadline:
                    break
        finally:
            # Flush partial buffer so we keep the last incomplete chunk.
            self.stop(flush_partial=True)

        if not collected:
            return

        audio = np.concatenate(collected)
        max_samples = int(round(duration_sec * self.sr))
        audio = audio[:max_samples]
        self._write_wav(Path(output_path), audio, self.sr)


if __name__ == "__main__":
    ap = AudioProcessor(chunk_sec=5.0)
    duration = 5.0
    outfile = Path("recording.wav")
    print(f"Recording {duration:.1f}s of audio to {outfile} ...")
    ap.record_wav(outfile, duration)
    print(f"Saved WAV to {outfile.resolve()}")

    outfile = str(outfile.resolve())

    from mlx_audio.stt.generate import generate_transcription
    model = "mlx-community/whisper-large-v3-turbo"
    segments = generate_transcription(
        model=model,
        audio_path=outfile,
        output_path="",
        verbose=True,
    )
    breakpoint()