import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Force load .env file explicitly
load_dotenv(dotenv_path=".env")

intents = discord.Intents.default()
intents.message_content = True  # needed for reading messages

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command()
async def hello(ctx):
    await ctx.send("Hello from Hedwig!")

# Get token from environment
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token found. Did you set DISCORD_TOKEN in .env?")

bot.run(TOKEN)
