from typing import Any, Optional

import discord


class LayoutView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = 180.0) -> None: ...
    def content_length(self) -> int: ...


class Container(discord.ui.Item):
    def __init__(self, *children: Any, accent_color: Optional[int] = None) -> None: ...


class Section(discord.ui.Item):
    def __init__(self, *children: Any, accessory: Any = ...) -> None: ...


class TextDisplay(discord.ui.Item):
    def __init__(self, content: str) -> None: ...


class Thumbnail(discord.ui.Item):
    def __init__(self, media: str, *, description: str = ...) -> None: ...


class Separator(discord.ui.Item):
    def __init__(
        self,
        *,
        visible: bool = ...,
        spacing: Any = ...,
    ) -> None: ...


class ActionRow(discord.ui.Item):
    def __init__(self, *children: Any) -> None: ...
