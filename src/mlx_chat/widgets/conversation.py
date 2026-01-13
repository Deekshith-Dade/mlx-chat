import llm
from textual import containers, getters, on, work
from textual.app import ComposeResult
from textual.reactive import reactive, var
from textual.widgets import Input

from mlx_chat.agent.agent import AgentBase, AgentFail, AgentReady
from mlx_chat.widgets.throbber import Throbber
from mlx_chat.widgets.user_input import UserInput
from mlx_chat.widgets.response import Response, ResponseUpdate


SYSTEM = "You are the HAL 9000 the AI from the movie 2001 Space Odyssey and you are sentient. Have fun with user pretending you are this."

class Conversation(containers.Vertical):
    
    BINDING_GROUP_TITLE = "Conversation"
    model_name = var("gemini-2.5-flash")
    busy_count = var(0)
    
    throbber: getters.query_one(Throbber) = getters.query_one("#throbber")

    agent: var[AgentBase | None] = var(None, bindings=True)
    

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name
        self._agent_response: Response | None = None
    
    async def on_mount(self) -> None:
        def start_agent() -> None:
            # from mlx_chat.agent.llm_agent import LLMAgent
            from mlx_chat.agent.mlx_vlm_agent import MLXVLMAgent

            self.agent = MLXVLMAgent(self.model_name) 
            self.agent.start(self)

        self.call_after_refresh(start_agent)
    
    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        with containers.Vertical(id="chat-view"):
            yield Input(placeholder="How can I help you?", id="input-area")
 
    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        chat_view = self.query_one("#chat-view")
        event.input.clear()
        await chat_view.mount(userInput := UserInput(event.value))
        userInput.scroll_visible()
        self._agent_response = response = Response()
        await chat_view.mount(response)
        response.border_title = self.model_name.upper()
        self.send_prompt_to_agent(event.value)
    
    @on(ResponseUpdate)
    async def on_response_update(self, event: ResponseUpdate) -> None:
        event.stop()
        if self._agent_response is not None:
            await self._agent_response.append_fragment(event.text)
            self._agent_response.scroll_visible()
        
    @on(AgentFail)
    async def on_agent_fail(self, event: AgentFail) -> None:
        event.stop()
        if self._agent_response is not None:
            await self._agent_response.append_fragment(event.details)
        else:
            chat_view = self.query_one("#chat-view")
            await chat_view.mount(response := Response(event.details))
            response.anchor()

    @on(AgentReady)
    async def on_agent_ready(self, event: AgentReady) -> None:
        event.stop()
        message = f"{self.model_name} is ready for Inquiry."
        if self._agent_response is not None:
            await self._agent_response.append_fragment(message)
        else:
            chat_view = self.query_one("#chat-view")
            await chat_view.mount(response := Response(message))
            response.anchor()


    async def watch_model_name(self, model_name: str) -> None:
        if self.agent is not None:
            try:
                await self.agent.change_model(model_name)
            except Exception as e:
                print(f"Model name not found")
                raise 

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")
        
    @work(thread=True)
    async def send_prompt_to_agent(self, prompt: str) -> None:
        if self.agent is not None:
            self.busy_count += 1
            try:
                await self.agent.send_prompt(prompt)
            except llm.UnknownModelError as error:
                chat_view = self.query_one("#chat-view")
                await chat_view.mount(UserInput(error))
            finally:
                self.busy_count -= 1
            self.call_later(self.agent_turn_over, "end_turn")
            
            
    async def agent_turn_over(self, stop_reason: str | None = "end_turn") -> None:
        # elaborate more on stop_reason
        self._agent_response = None


            


