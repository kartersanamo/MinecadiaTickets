import discord


class ManageTicketsSupport:
    @staticmethod
    async def update_msg(interaction: discord.Interaction) -> None:
        """Hook for refreshing public ticket panel messages after config edits."""
        _ = interaction
