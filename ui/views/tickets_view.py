import discord
import json
from core.config import get_data
from services.ticket_creation_service import TicketCreationService as TicketSystem


class TicketsView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout = None)
        self.data = get_data()
        self.tickets: dict 
        self.ticket_manager: TicketSystem = TicketSystem()

        with open('assets/tickets.json', 'r') as file:
            tickets = json.load(file)
            del tickets['TOGGLE_STATUS']
            self.tickets = tickets 

        for category_name, category_info in list(self.tickets.items())[:5]:
            select_options = [
                discord.SelectOption(
                    label = option_name,
                    emoji = option_info['Emoji'],
                    description = option_info['Description']
                )
                for option_name, option_info in category_info.items()
                if option_name != "Role"
            ]

            select = discord.ui.Select(
                custom_id = category_name,
                placeholder = category_name,
                options = select_options
            )
            select.callback = self.handle_selection
            self.add_item(select)

    async def handle_selection(self, interaction: discord.Interaction):
        await self.ticket_manager.new_ticket(interaction, self)
