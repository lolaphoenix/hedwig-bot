import os
import discord
from discord.ext import commands

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
bot.run(TOKEN)
