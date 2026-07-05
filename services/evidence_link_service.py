import discord

from core.loggers import log_tasks


def is_evidence_or_video_field(label: str) -> bool:
    lower = label.lower()
    return "evidence" in lower or "video" in lower


def is_link(word: str) -> bool:
    return "http://" in word or "https://" in word


async def resend_evidence_links(channel: discord.TextChannel, label: str, value: str) -> None:
    if not value or not is_evidence_or_video_field(label):
        return

    for word in value.split():
        if not is_link(word):
            continue
        try:
            await channel.send(word)
        except discord.HTTPException as e:
            log_tasks.error(
                "Failed to resend evidence link in #%s (%s): %s",
                channel.name,
                channel.id,
                e,
            )
