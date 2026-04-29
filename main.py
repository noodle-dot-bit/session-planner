# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=line-too-long
import os
import datetime
import discord
from dotenv import load_dotenv
from tinydb import TinyDB, Query

db = TinyDB('db.json')
query = Query()

load_dotenv()
bot = discord.Bot()

@bot.event
async def on_ready():
    # Register the persistent view on startup so it survives reboots
    bot.add_view(NormalView())
    print(f"{bot.user} is ready and online!")

# --- HELPER FUNCTIONS ---
def generate_session_embed(session_data) -> discord.Embed:
    if not session_data:
        session_data = {}

    name = session_data.get("name", "Session")
    time = session_data.get("time", "None")
    agenda = session_data.get("agenda", "None")
    outfit = session_data.get("outfit", "None")
    supplies = session_data.get("supplies", "None")
    pretasks = session_data.get("pretasks", "None")
    confirmed = session_data.get("confirmed", False)

    time_seconds = time[3:-3] if len(time) > 6 else "0"
    
    status_text = "✅ **Ready & Confirmed!**" if confirmed else "⏳ *Waiting for confirmation...*"
    embed_color = discord.Color.green() if confirmed else 8388837

    embed = discord.Embed(
        description=(
            f"# {name}\n"
            "## Time:\n"
            f"<t:{time_seconds}:F>\n<t:{time_seconds}:R>\n"
            "## Agenda:\n"
            f"{agenda}\n"
            "## Outfit:\n"
            f"{outfit}\n"
            "## Toys & Materials Needed:\n"
            f"{supplies}\n"
            "## Pre-Session Tasks:\n"
            f"{pretasks}\n"
            "### Confirmation Status:\n"
            f"{status_text}\n\n"
        ),
        color=embed_color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text="Last Edit")
    return embed

def get_configured_normal_view(message_id: int):
    """Helper to generate the view with the correct button colors/labels based on the database."""
    session_data = db.get(query.message_id == message_id)
    is_confirmed = session_data.get("confirmed", False) if session_data and not isinstance(session_data, list) else False
    return NormalView().configure_buttons(is_confirmed)


# --- MODALS & VIEWS ---
class SingleEditModal(discord.ui.Modal):
    def __init__(self, message_id: int, field_name: str, current_value: str):
        super().__init__(title=f"Edit {field_name.capitalize()}"[:45])
        self.message_id = message_id
        self.field_name = field_name
        
        style = discord.InputTextStyle.short if field_name in ["name", "time"] else discord.InputTextStyle.paragraph
        
        self.add_item(discord.ui.InputText(
            label=f"New {field_name.capitalize()}"[:45],
            style=style,
            value=str(current_value) if current_value else "", 
            required=False
        ))

    async def callback(self, interaction: discord.Interaction):
        child = self.children[0]
        new_value = child.value if isinstance(child, discord.ui.InputText) else ""
        
        db.update({self.field_name: new_value}, query.message_id == self.message_id)

        raw_data = db.get(query.message_id == self.message_id)
        updated_data = dict(raw_data) if raw_data and not isinstance(raw_data, list) else {}
        new_embed = generate_session_embed(updated_data) 

        # Use the helper function to build the view safely
        await interaction.response.edit_message(embed=new_embed, view=get_configured_normal_view(self.message_id))
        await interaction.followup.send(f"Successfully updated the {self.field_name}!", ephemeral=True)


class EditDropdownView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.selected_field = None 

    @discord.ui.select(
        placeholder="Choose a field to edit...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Name", value="name", emoji="🏷️"),
            discord.SelectOption(label="Time", value="time", emoji="⏰", description="Use Discord timestamp format"),
            discord.SelectOption(label="Agenda", value="agenda", emoji="📋"),
            discord.SelectOption(label="Outfit", value="outfit", emoji="👗"),
            discord.SelectOption(label="Supplies", value="supplies", emoji="🧸"),
            discord.SelectOption(label="Pre-tasks", value="pretasks", emoji="✅")
        ]
    )
    async def select_callback(self, select, interaction: discord.Interaction):
        self.selected_field = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Open Edit Menu", style=discord.ButtonStyle.primary, emoji="📝")
    async def open_modal_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self.selected_field:
            await interaction.response.send_message("Please select a field from the dropdown first!", ephemeral=True)
            return

        session_data = db.get(query.message_id == self.message_id)
        if not session_data or isinstance(session_data, list):
            await interaction.response.send_message("Session not found in the database.", ephemeral=True)
            return

        raw_value = session_data.get(self.selected_field, "")
        current_value = str(raw_value) if raw_value else ""
        
        await interaction.response.send_modal(
            SingleEditModal(self.message_id, self.selected_field, current_value)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(view=get_configured_normal_view(self.message_id))


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Yes, Permanently Delete", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_delete(self, button: discord.ui.Button, interaction: discord.Interaction):
        db.remove(query.message_id == self.message_id)

        await interaction.response.edit_message(
            content="🗑️ **This session has been permanently deleted.**", 
            embed=None, 
            view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def cancel_delete(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(view=get_configured_normal_view(self.message_id))


class NormalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Required for persistent views

    def configure_buttons(self, is_confirmed: bool):
        """Dynamically styles the first button based on database confirmation state."""
        if not self.children:
            return self
            
        first_button = self.children[0]
        # PYLANCE FIX: Type checking the button before assigning attributes
        if isinstance(first_button, discord.ui.Button):
            if is_confirmed:
                first_button.label = "Cancel Confirmation"
                first_button.style = discord.ButtonStyle.danger
                first_button.emoji = "✖️"
            else:
                first_button.label = "Confirm Readiness"
                first_button.style = discord.ButtonStyle.success
                first_button.emoji = "✅"
        return self

    @discord.ui.button(label="Confirm Readiness", style=discord.ButtonStyle.success, emoji="✅", custom_id="btn_persistent_ready")
    async def toggle_ready(self, button: discord.ui.Button, interaction: discord.Interaction):
        # PYLANCE FIX: Ensuring interaction.message exists
        if not interaction.message:
            await interaction.response.send_message("Error: Message not found.", ephemeral=True)
            return
            
        message_id = interaction.message.id 
        session_data = db.get(query.message_id == message_id)
        
        if not session_data or isinstance(session_data, list):
            await interaction.response.send_message("Session not found in the database.", ephemeral=True)
            return

        if interaction.user and interaction.user.id == session_data.get("author_id"):
            await interaction.response.send_message("You cannot confirm your own scheduled session!", ephemeral=True)
            return

        current_state = session_data.get("confirmed", False)
        new_state = not current_state  
        db.update({"confirmed": new_state}, query.message_id == message_id)

        if new_state:
            response_msg = "You have confirmed you are ready!"
        else:
            response_msg = "You have canceled your confirmation."

        raw_data = db.get(query.message_id == message_id)
        updated_data = dict(raw_data) if raw_data and not isinstance(raw_data, list) else {}
        
        new_embed = generate_session_embed(updated_data)
        new_view = NormalView().configure_buttons(new_state)
        
        await interaction.response.edit_message(embed=new_embed, view=new_view)
        await interaction.followup.send(response_msg, ephemeral=True)

    @discord.ui.button(label="Edit Session", style=discord.ButtonStyle.secondary, emoji="✏️", custom_id="btn_persistent_edit")
    async def edit_session(self, button: discord.ui.Button, interaction: discord.Interaction):
        # PYLANCE FIX: Ensuring interaction.message exists
        if not interaction.message:
            await interaction.response.send_message("Error: Message not found.", ephemeral=True)
            return
            
        message_id = interaction.message.id
        session_data = db.get(query.message_id == message_id)
        
        if not session_data or isinstance(session_data, list):
            await interaction.response.send_message("Session not found in the database.", ephemeral=True)
            return

        db_author = session_data.get("author_id")
        if interaction.user and db_author and interaction.user.id != db_author:
            await interaction.response.send_message("Only the person who scheduled this session can edit it!", ephemeral=True)
            return

        await interaction.response.edit_message(view=EditDropdownView(message_id))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="btn_persistent_delete")
    async def delete_session_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # PYLANCE FIX: Ensuring interaction.message exists
        if not interaction.message:
            await interaction.response.send_message("Error: Message not found.", ephemeral=True)
            return
            
        message_id = interaction.message.id
        session_data = db.get(query.message_id == message_id)
        
        if not session_data or isinstance(session_data, list):
            await interaction.response.send_message("Session not found in the database.", ephemeral=True)
            return

        db_author = session_data.get("author_id")
        if interaction.user and db_author and interaction.user.id != db_author:
            await interaction.response.send_message("Only the creator of this session can delete it!", ephemeral=True)
            return

        await interaction.response.edit_message(view=ConfirmDeleteView(message_id))


# --- COMMANDS ---
@bot.slash_command(
    name="schedule",
    description="Schedule a session",
    integration_types={
        discord.IntegrationType.user_install
    },
    contexts={
        discord.InteractionContextType.guild,
        discord.InteractionContextType.bot_dm,
        discord.InteractionContextType.private_channel
    }
)
@discord.option("name", description="Name of the session", default="Session", required=False)
@discord.option("time", description="Time the session will take place")
@discord.option("agenda", description="Agenda for the session", default="None", required=False)
@discord.option("outfit", description="Outfit for the session", default="None", required=False)
@discord.option("supplies", description="Toys and supplies needed for the session", default="None", required=False)
@discord.option("pretasks", description="Pre-session tasks to be completed", default="None", required=False)
async def schedule(ctx, name: str = "Session", time: str = "None", agenda: str = "None", outfit: str = "None", supplies: str = "None", pretasks: str = "None"):

    initial_data = {
        "name": name,
        "time": time,
        "agenda": agenda,
        "outfit": outfit,
        "supplies": supplies,
        "pretasks": pretasks,
        "confirmed": False
    }

    embed = generate_session_embed(initial_data)

    interaction = await ctx.respond(embed=embed)
    msg = await interaction.original_response()

    db.insert({
        "message_id": msg.id,
        "author_id": ctx.author.id,
        "name": name,
        "time": time,
        "agenda": agenda,
        "outfit": outfit,
        "supplies": supplies,
        "pretasks": pretasks,
        "confirmed": False
    })

    # Use the helper function so the button styles initialize properly
    await msg.edit(view=get_configured_normal_view(msg.id))


bot.run(os.getenv('TOKEN'))