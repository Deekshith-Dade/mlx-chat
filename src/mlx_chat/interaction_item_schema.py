

from typing import NotRequired, TypedDict


class InteractionItemSchema(TypedDict):
    item_name:  str
    """A unique item name which defines the kind of interactions users are expecting,
    should be things like 'Chat', 'TTS', 'STT', 'STS', 'Imagen', 'VideoGen' and other applications"""
    display_name: str
    description: str
