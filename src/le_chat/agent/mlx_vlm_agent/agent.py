import asyncio
import threading
from dataclasses import dataclass
from typing import List, Optional

from mlx_vlm import apply_chat_template
from mlx_vlm.generate import stream_generate, load

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
    
    def _update_loading_status(self, status: str) -> None:
        self.post_message(AgentLoading(status))

    def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        try:
            model, processor = load(self.model_name, local_files_only=True)
            self.agent = model
            self.processor = processor
            self.post_message(AgentReady())
        except Exception:
            self._update_loading_status(f"Downloading {self.model_name}...")
            try:
                if download_model(self.model_name, self._update_loading_status):
                    self._update_loading_status(f"Loading {self.model_name}...")
                    model, processor = load(self.model_name, local_files_only=True)
                    self.agent = model
                    self.processor = processor
                    self.post_message(AgentReady())
                else:
                    self.post_message(AgentFail("Download failed", f"Failed to download {self.model_name}"))
            except Exception as e:
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
        messages = [
            mess.to_dict()
            for mess in self.history
        ]
        messages = []
        images = []
        audio = []
        for mess in self.history:
            # message = mess.to_dict()
            messages.append({
                "role": mess.role,
                "content": mess.content,
            })
            images.extend(mess.images or [])
            audio.extend(mess.audio or [])

        messages = apply_chat_template(
            self.processor, self.agent.config, messages, num_images=len(images), num_audios=1 if len(audio) else 0
        )
        print(messages)
        return messages, images, audio
        
    async def send_prompt(self, prompt: str) -> str | None:
        mlxvlm_prompt = build_prompt(prompt)
        user_input = MLXVLMMessageContainer(
            role="user",
            content=mlxvlm_prompt.prompt,
            images=mlxvlm_prompt.images,
            audio=mlxvlm_prompt.audio,
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
            for response in stream_generate(
                self.agent, 
                self.processor, 
                prompt, 
                image = images if len(images) else None, 
                # Currently supports one audio file
                audio=audio[-1:] if len(audio) else None,
                max_tokens=self.max_tokens,
                skip_special_tokens=False,
            ):
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
        
        

        
