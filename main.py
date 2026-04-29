# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=line-too-long
import os
# import uuid
import datetime
import discord
from dotenv import load_dotenv
from tinydb import TinyDB, Query

load_dotenv() # load all the variables from the env file
bot = discord.Bot()

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

@bot.slash_command(
    name="schedule",
    description="Schedule a session",
    integration_types={
        discord.IntegrationType.user_install
    },
    contexts={
        discord.InteractionContextType.guild,           # Inside servers
        discord.InteractionContextType.bot_dm,          # In DMs directly with the bot
        discord.InteractionContextType.private_channel  # In DMs with other users or Group DMs
    }
)
@discord.option("name", description="Name of the session", default="Session", required=False) # Option for the name of the session
@discord.option("time", description="Time the session will take place") # Option for the time of the session
@discord.option("agenda", description="Agenda for the session", default="None", required=False) # Option for the agenda of the session
@discord.option("outfit", description="Outfit for the session", default="None", required=False) # Option for the outfit for the session
@discord.option("supplies", description="Toys and supplies needed for the session", default="None", required=False) # Option for the supplies needed for the session
@discord.option("pretasks", description="Pre-session tasks to be completed", default="None", required=False) # Option for the pretasks for the session
async def schedule(ctx, name: str = "Session", time: str = "None", agenda: str = "None", outfit: str = "None", supplies: str = "None", pretasks: str = "None"):

    timeSeconds = time[3:-3] # Removes the <t: and :R> from the timestamp to get just the seconds

    # Create an embed with the session details
    embed = discord.Embed(
    description=(
        f"# {name}\n"
        "## Time:\n"
        f"<t:{timeSeconds}:F>\n<t:{timeSeconds}:R>\n"
        "## Agenda:\n"
        f"{agenda}\n"
        "## Outfit:\n"
        f"{outfit}\n"
        "## Toys & Materials Needed:\n"
        f"{supplies}\n"
        "## Pre-Session Tasks:\n"
        f"{pretasks}\n"
    ),
    color=8388837,
    timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text="Last Edit")
    await ctx.respond(embed=embed) # Send the embed as a response to the command

bot.run(os.getenv('TOKEN')) # run the bot with the token
