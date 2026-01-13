import os

import llm
from llm.models import dataclass

from textual.message import Message
from textual.message_pump import MessagePump
from mlx_chat.agent.agent import AgentBase, AgentFail, AgentLoading, AgentReady, MessageContainer, MessageDetails
from mlx_chat.widgets.response import ResponseUpdate

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@dataclass
class LLMMessageDetails(MessageDetails):
    usage: dict
    model: str
    finish_reason: str
    id: str

@dataclass
class LLMMessageContainer(MessageContainer):
    """"""
    

class LLMAgent(AgentBase):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        self.agent = None
        # session stuff later

    def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        self.post_message(AgentLoading())
        # logging 
        try:
            model = llm.get_model(self.model_name)
            key = GEMINI_API_KEY if "gemini" in self.model_name else OPENAI_API_KEY
            model.key = key
            self.agent = model.conversation()
            self.post_message(AgentReady())
        except Exception as e:
            print(f"Exception {e}")
            self.post_message(AgentFail(e, "Probably Model name is wrong"))
            
    
    async def change_model(self, model_name: str) -> bool | None:
        self.model_name = model_name
        self.start(self._message_target)


    async def send_prompt(self, prompt: str) -> str | None:
        self.history.append(LLMMessageContainer(role="user", content=prompt))
        if self.agent is None: 
            self.post_message(AgentFail("Agent Not available", "Agent Not available"))
            return
        try:
            llm_response = self.agent.prompt(prompt)
            response_content = ""
            for chunk in llm_response:
                response_content += chunk
                self.post_message(ResponseUpdate(text=chunk))
        except Exception as e:
            print(f"Exception: {e}")
            self.post_message(AgentFail(e, "Failed During Generation"))
        
        
        
                