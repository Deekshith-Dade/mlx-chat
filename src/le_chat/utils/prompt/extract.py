from pathlib import Path
import re
from typing import Iterable, Set

from le_chat.utils.prompt.resource import ResourceType, load_resource, ResourceUnsupportedType, ResourceReadError


RE_MATCH_FILE_PROMPT = re.compile(r"@(\S+)|@\"(.*)\"")


def extract_paths_from_prompt(prompt: str) -> Iterable[tuple[str, int, int]]:
    """Find file syntax in prompts.

    Args:
        prompt: A line of prompt.

    Yields:
        A tuple of (PATH, START, END).
    """
    for match in RE_MATCH_FILE_PROMPT.finditer(prompt):
        path, quoted_path = match.groups()
        yield (path or quoted_path, match.start(0), match.end(0))


def validate_input_files(
    prompt: str,
    allowed_types: Set[ResourceType] | None = None
) -> tuple[bool, str]:
    """Validate that all file references in the prompt exist and are of allowed types.
    
    Args:
        prompt: The user prompt potentially containing @file references.
        allowed_types: Set of allowed resource types (e.g., {"audio"}, {"audio", "text", "image"}).
                      If None, all types are allowed (text, image, audio).
    
    Returns:
        A tuple of (success: bool, message: str).
    """
    if allowed_types is None:
        allowed_types = {"text", "image", "audio"}
    
    for path, _, _ in extract_paths_from_prompt(prompt):
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return False, f"{file_path} File not found."
        
        try:
            resource = load_resource(file_path)
            if resource.resource_type not in allowed_types:
                allowed_str = ", ".join(sorted(allowed_types))
                return False, f"'{file_path.name}' is {resource.resource_type}, but only {allowed_str} allowed."
        except ResourceUnsupportedType as e:
            return False, str(e)
        except ResourceReadError as e:
            return False, str(e)
    
    return True, "All files valid."


if __name__ == "__main__":
    prompt = """This is a new thing that I'm testing let's see how it
works. There is a file @file/file.py and I will see how
the printing will happen
    """

    # Replace all file paths with the special character <special>
    result = []
    last_index = 0
    for path, a, b in extract_paths_from_prompt(prompt):
        result.append(prompt[last_index:a])
        result.append("<special>")
        last_index = b
    result.append(prompt[last_index:])
    replaced_prompt = "".join(result)

    print(replaced_prompt)
    print(type(replaced_prompt))

    # Validate with all types allowed (default)
    print(f"Validation (all types): {validate_input_files(prompt)}")
    
    # Validate with only audio allowed
    print(f"Validation (audio only): {validate_input_files(prompt, allowed_types={'audio'})}")