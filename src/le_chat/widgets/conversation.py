from asyncio import sleep
from pathlib import Path
import llm
from textual import containers, getters, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive, var
from textual.widgets import Input

from le_chat.agent.agent import AgentBase, AgentFail, AgentLoading, AgentReady
from le_chat.app import ChatApp
from le_chat.utils.prompt.extract import extract_paths_from_prompt, validate_input_files
from le_chat.widgets.prompt import Prompt, UserInputSubmitted
from le_chat.widgets.throbber import Throbber
from le_chat.widgets.user_input import UserInput
from le_chat.widgets.response import Response, ResponseMetadataUpdate, ResponseUpdate


SYSTEM = "You are the HAL 9000 the AI from the movie 2001 Space Odyssey and you are sentient. Have fun with user pretending you are this."

class Conversation(containers.Vertical):
    
    BINDING_GROUP_TITLE = "Conversation"
    BINDINGS = [
        Binding(
            "ctrl+c,escape",
            "cancel_generation",
            "Stop Generation",
            key_display="Ctrl+C / Esc",
            tooltip="Stop the current generation",
            priority=True,
        ),
    ]
    
    model_name = var("gpt-4o")
    busy_count = var(0)
    
    throbber: getters.query_one(Throbber) = getters.query_one("#throbber")

    agent: var[AgentBase | None] = var(None, bindings=True)
    # mlx-community/gemma-3n-E2B-it-4bit
    # mlx-community/gemma-3-12b-it-qat-4bit
    # lmstudio-community/gemma-3n-E4B-it-MLX-8bit
    # lmstudio-community/Qwen3-VL-4B-Instruct-MLX-4bit
    # mlx-community/medgemma-1.5-4b-it-4bit
    model_name: var[str | None] = var("lmstudio-community/Qwen3-VL-4B-Instruct-MLX-4bit")

    def __init__(self):
        super().__init__()
        self._agent_response: Response | None = None
    
    async def on_mount(self) -> None:
        self.post_message(AgentLoading(loading_message=f"Loading {self.model_name}..."))
        self.call_after_refresh(self.start_agent)
            
    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        with containers.Vertical(id="chat-layout"):
            yield containers.Vertical(id="chat-view")
            yield Prompt(id="user-prompt")
 
    @work(thread=True)
    async def start_agent(self) -> None:
        # from le_chat.agent.llm_agent import LLMAgent as Agent
        from le_chat.agent.mlx_vlm_agent import MLXVLMAgent as Agent
        self.agent = Agent(self.model_name) 
        self.agent.start(self)


    @on(UserInputSubmitted)
    async def on_input(self, event: UserInputSubmitted) -> None:
        event.stop()
        success, msg = validate_input_files(event.body)
        prompt_widget: Prompt = self.query_one("#user-prompt")
        if not success:
            prompt_widget.warning_message = msg
            return
        else:
            prompt_widget.clear()

            
        chat_view = self.query_one("#chat-view")
        await chat_view.mount(userInput := UserInput(event.body))
        userInput.scroll_visible()
        self._agent_response = response = Response()
        await chat_view.mount(response)
        response.scroll_to_center(self)
        response.border_title = self.model_name.upper()
        self.send_prompt_to_agent(event.body)
    
    @on(ResponseUpdate)
    async def on_response_update(self, event: ResponseUpdate) -> None:
        event.stop()
        if self._agent_response is not None:
            await self._agent_response.append_fragment(event.text)
            self._agent_response.scroll_visible()
        
    @on(ResponseMetadataUpdate)
    async def on_response_metadata_update(self, event: ResponseMetadataUpdate) -> None:
        event.stop()
        if self._agent_response is not None:
            await self._agent_response.update_border_subtitle(event)
            self._agent_response.scroll_visible()

    @on(AgentFail)
    async def on_agent_fail(self, event: AgentFail) -> None:
        if self._agent_response is not None:
            await self._agent_response.append_fragment(f"{event.details} : {event.message}")
        else:
            chat_view = self.query_one("#chat-view")
            await chat_view.mount(response := Response(f"{event.details} : {event.message}"))
            response.anchor()

    @on(AgentReady)
    async def on_agent_ready(self, event: AgentReady) -> None:
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
    
    async def action_cancel_generation(self) -> None:
        """Cancel the current generation if in progress."""
        if self.agent is not None and self.busy_count > 0:
            cancelled = await self.agent.cancel()
            if cancelled:
                self.call_later(self.agent_turn_over, "cancelled")


            


