import asyncio
import threading
from dataclasses import dataclass
from typing import List, Optional

from mlx_vlm import apply_chat_template as vlm_apply_chat_template
from mlx_vlm import load as vlm_load
from mlx_vlm.generate import stream_generate as vlm_stream_generate

from mlx_lm import load as lm_load
from mlx_lm.generate import stream_generate as lm_stream_generate

from textual.message_pump import MessagePump
from le_chat.agent.agent import AgentBase, AgentFail, AgentReady, AgentLoading, MessageContainer, MessageDetails
from le_chat.agent.huggingface_utils import download_model
from le_chat.widgets.response import ResponseUpdate, ResponseMetadataUpdate
from le_chat.agent.mlx_vlm_agent.prompt import build as build_prompt


@dataclass
class MLXVLMMessageDetails(MessageDetails):
    prompt_tokens: int = 0
    generation_tokens: int = 0
    total_tokens: int = 0
    prompt_tps: float = 0.0
    generation_tps: float = 0.0
    peak_memory: float = 0.0

@dataclass
class MLXVLMMessageContainer(MessageContainer):
    role: str
    content: str
    details: Optional[MLXVLMMessageDetails] = None
    images: Optional[List[str]] = None
    audio: Optional[List[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "images": self.images,
            "audio": self.audio
        }

class MLXVLMAgent(AgentBase):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        self.agent = None
        self.processor = None
        self.max_tokens = 2048
        self.history: List[MLXVLMMessageContainer] = []
        self._cancel_event: threading.Event = threading.Event()
        self._is_generating: bool = False
        self._is_vlm: bool = True  # Default to VLM, will be set during loading
    
    def _update_loading_status(self, status: str) -> None:
        self.post_message(AgentLoading(status))

    def _load_model(self, local_files_only: bool = True):
        """
        Try to load the model, first as VLM, then fall back to LM.
        Returns (model, processor, is_vlm) tuple.
        
        Only falls back to LM if VLM explicitly says the model type is not supported.
        Other errors (like file not found) are re-raised to trigger download.
        """
        try:
            model, processor = vlm_load(self.model_name, local_files_only=local_files_only)
            return model, processor, True
        except ValueError as e:
            if "not supported" in str(e).lower():
                try:
                    model, processor = lm_load(self.model_name)
                    return model, processor, False
                except Exception as lm_error:
                    raise lm_error
            raise

    def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        try:
            model, processor, is_vlm = self._load_model(local_files_only=True)
            self.agent = model
            self.processor = processor
            self._is_vlm = is_vlm
            self.post_message(AgentReady())
        except Exception:
            self._update_loading_status(f"Downloading {self.model_name}...")
            try:
                if download_model(self.model_name, self._update_loading_status):
                    self._update_loading_status(f"Loading {self.model_name}...")
                    model, processor, is_vlm = self._load_model(local_files_only=True)
                    self.agent = model
                    self.processor = processor
                    self._is_vlm = is_vlm
                    self.post_message(AgentReady())
                else:
                    self.post_message(AgentFail("Download failed", f"Failed to download {self.model_name}"))
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                self.post_message(AgentFail(str(e), "Loading failed"))
    
    async def change_model(self, model_name: str) -> bool | None:
        self.model_name = model_name
        self.start(self._message_target)
    
    async def cancel(self) -> bool:
        """Cancel the current generation if in progress."""
        # Always allow setting the cancel event - the generation loop will check it
        # This handles the race condition where cancel is called before _is_generating is set
        if not self._cancel_event.is_set():
            print(f"Setting Cancel Event at the agent")
            self._cancel_event.set()
            return True
        # Event already set (cancellation already requested)
        return False
    
    def _prepare_messages(self) -> str:
        messages = []
        images = []
        audio = []
        for mess in self.history:
            messages.append({
                "role": mess.role,
                "content": mess.content,
            })
            images.extend(mess.images or [])
            audio.extend(mess.audio or [])

        if self._is_vlm:
            # VLM: Use mlx_vlm's apply_chat_template
            formatted_prompt = vlm_apply_chat_template(
                self.processor, self.agent.config, messages, 
                num_images=len(images), num_audios=1 if len(audio) else 0
            )
        else:
            # LM: Use the tokenizer's apply_chat_template directly
            formatted_prompt = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, return_dict=False
            )
        
        print(formatted_prompt)
        return formatted_prompt, images, audio
        
    def _stream_generate(self, prompt, images, audio):
        """
        Generator that yields responses from the appropriate stream_generate function
        based on whether the model is VLM or LM.
        """
        if self._is_vlm:
            # VLM: Use mlx_vlm's stream_generate with image/audio support
            yield from vlm_stream_generate(
                self.agent, 
                self.processor, 
                prompt, 
                image=images if len(images) else None, 
                # Currently supports one audio file
                audio=audio[-1:] if len(audio) else None,
                max_tokens=self.max_tokens,
                skip_special_tokens=False,
            )
        else:
            # LM: Use mlx_lm's stream_generate (no image/audio support)
            yield from lm_stream_generate(
                self.agent, 
                self.processor, 
                prompt, 
                max_tokens=self.max_tokens,
            )

    async def send_prompt(self, prompt: str) -> str | None:
        mlxvlm_prompt = build_prompt(prompt)
        user_input = MLXVLMMessageContainer(
            role="user",
            content=mlxvlm_prompt.prompt,
            images=mlxvlm_prompt.images if self._is_vlm else None,
            audio=mlxvlm_prompt.audio if self._is_vlm else None,
        )
        self.history.append(user_input)

        if self.agent is None:
            self.post_message(AgentFail("Agent Not available", "Agent Not available"))
            return 

        text = ""
        self._cancel_event.clear()
        self._is_generating = True
        try:
            prompt, images, audio = self._prepare_messages()
            print(audio)
            last_response = None
            
            # This method is already running in a thread (via @work(thread=True)),
            # so we can do blocking work directly here and check cancellation between iterations
            for response in self._stream_generate(prompt, images, audio):
                # Check for cancellation between iterations
                if self._cancel_event.is_set():
                    self.post_message(ResponseUpdate(text="\n\n[Generation cancelled by user]"))
                    break
                    
                text += response.text
                self.post_message(ResponseUpdate(text=response.text))
                last_response = response
            
            # Check if generation was cancelled
            was_cancelled = self._cancel_event.is_set()
            
            if not was_cancelled and last_response is not None:
                metadata = dict(
                    prompt_tokens=getattr(last_response, "prompt_tokens", None),
                    generation_tokens=getattr(last_response, "generation_tokens", None),
                    total_tokens=getattr(last_response, "total_tokens", None),
                    prompt_tps=getattr(last_response, "prompt_tps", None),
                    generation_tps=getattr(last_response, "generation_tps", None),
                    peak_memory=getattr(last_response, "peak_memory", None),
                )
                
                details = MLXVLMMessageDetails(**metadata)
                message = ResponseMetadataUpdate(**metadata)
                self.post_message(message)
                
                self.history.append(MLXVLMMessageContainer(
                    role="assistant", 
                    content=text, 
                    details=details
                ))
            elif text:  # Cancelled but we have partial text - save without metadata
                self.history.append(MLXVLMMessageContainer(
                    role="assistant", 
                    content=text, 
                    details=None
                ))

        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            self.history.pop()
            self.post_message(AgentFail(e, "Failed During Generation"))
        finally:
            self._is_generating = False
            self._cancel_event.clear()

if __name__ == "__main__":
    model = "mlx-community/gemma-3n-E2B-it-4bit"
    agent = MLXVLMAgent(model)
    prompt = "Transcribe the audio @/Users/deekshith/Downloads/sample.mp3"
    agent.start()
    asyncio.run(agent.send_prompt(prompt))
