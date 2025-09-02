import os
import discord
from discord.ext import commands
from dotenv import load_dotenv  # for loading environment variables

# Load environment variables from .env file
load_dotenv()

# Set up intents (needed for message content and commands)
intents = discord.Intents.default()
intents.message_content = True

# Create the bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Event: when the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

# Command: !hello
@bot.command()
async def hello(ctx):
    await ctx.send("Hello from Hedwig!")

# Get token from environment and run bot
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found. Did you set it in the .env file?")
bot.run(TOKEN)
