from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Literal, Optional
from le_chat.utils.prompt.extract import extract_paths_from_prompt
from le_chat.utils.prompt.resource import load_resource


@dataclass
class MLXVLMInput:
    prompt: str
    images: Optional[List[str]]
    audio: Optional[List[str]]

def build(prompt: str):
    result = []
    last_index = 0
    audio = []
    images = []
    for path, a, b in extract_paths_from_prompt(prompt):
        additional_token = ""
        resource = load_resource(Path(path))
        if resource.resource_type == 'text':
            additional_token = f"\nFile Path: {str(resource.path)}\n Content:\n {resource.text}\n"
        elif resource.resource_type == 'audio':
            additional_token = ""
            audio.append(str(resource.path))

        elif resource.resource_type == "image":
            additional_token = f"Image here: {str(resource.path)}"
            images.append(str(resource.path))
            
        result.append(prompt[last_index:a])
        result.append(additional_token)
        last_index = b
    result.append(prompt[last_index:])
    replaced_prompt = "".join(result)

    return MLXVLMInput(
        prompt=replaced_prompt,
        images=images,
        audio=audio
    )


if __name__ == "__main__":
    prompt = """This a test to see what the output is
So this is what it is there is a file here @/Users/deekshith/Downloads/escher.jpg
There is also @/Users/deekshith/Downloads/test.txt and a audio file @/Users/deekshith/Downloads/sample.mp3
"""
    print(build(prompt))