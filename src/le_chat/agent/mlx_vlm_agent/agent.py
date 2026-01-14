from dataclasses import dataclass
from typing import Optional
from mlx_vlm import apply_chat_template
from mlx_vlm.generate import stream_generate, load

from textual.message_pump import MessagePump
from le_chat.agent.agent import AgentBase, AgentFail, AgentReady, AgentLoading, MessageContainer, MessageDetails
from le_chat.widgets.response import ResponseUpdate, ResponseMetadataUpdate


@dataclass
class MLXVLMMessageDetails(MessageDetails):
    prompt_tokens: int = 0
    generation_tokens: int = 0
    total_tokens: int = 0
    prompt_tps: float = 0.0
    generation_tps: float = 0.0
    peak_memory: float = 0.0

class MLXVLMMessageContainer(MessageContainer):
    role: str
    content: str
    details: Optional[MLXVLMMessageDetails] = None
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content 
        }

class MLXVLMAgent(AgentBase):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        self.agent = None
        self.processor = None
        self.max_tokens = 2048
    
    def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        try:
            model, processor = load(self.model_name, local_files_only=True)
            self.agent = model
            self.processor = processor
            self.post_message(AgentReady())
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'Exception {e}')
            self.post_message(AgentFail(e, "Loading Failed From mlx"))
    
    async def change_model(self, model_name: str) -> bool | None:
        self.model_name = model_name
        self.start(self._message_target)
    
    def _prepare_messages(self) -> str:
        messages = [
            mess.to_dict()
            for mess in self.history
        ]

        messages = apply_chat_template(
            self.processor, self.agent.config, messages, num_images=0, num_audios=0
        )
        return messages
        
    async def send_prompt(self, prompt: str) -> str | None:
        self.history.append(MLXVLMMessageContainer(role="user", content=prompt))
        if self.agent is None:
            self.post_message(AgentFail("Agent Not available", "Agent Not available"))
            return 

        text = ""
        try:
            prompt = self._prepare_messages()
            last_response = None
            for response in stream_generate(
                self.agent, 
                self.processor, 
                prompt, 
                image = None, 
                audio = None,
                max_tokens = self.max_tokens
            ):
                text += response.text
                self.post_message(ResponseUpdate(text=response.text))
                last_response = response
            

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
                "assistant", text, details
            ))

        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            self.post_message(AgentFail(e, "Failed During Generation"))

if __name__ == "__main__":
    model = "mlx-community/gemma-3n-E2B-it-4bit"
    agent = MLXVLMAgent(model)
    agent.start()
        
        

        
