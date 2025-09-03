import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory storage for house points
house_points = {
    "gryffindor": 0,
    "slytherin": 0,
    "ravenclaw": 0,
    "hufflepuff": 0
}

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command()
async def hello(ctx):
    await ctx.send("Hello from Hedwig!")

@bot.command()
async def addpoints(ctx, house: str, points: int):
    house = house.lower()
    if house in house_points:
        house_points[house] += points
        await ctx.send(f"Added {points} points to {house.capitalize()}! Total: {house_points[house]}")
    else:
        await ctx.send("That house doesn't exist. Try Gryffindor, Slytherin, Ravenclaw, or Hufflepuff.")

@bot.command()
async def removepoints(ctx, house: str, points: int):
    house = house.lower()
    if house in house_points:
        house_points[house] -= points
        await ctx.send(f"Removed {points} points from {house.capitalize()}. Total: {house_points[house]}")
    else:
        await ctx.send("That house doesn't exist. Try Gryffindor, Slytherin, Ravenclaw, or Hufflepuff.")

@bot.command()
async def points(ctx):
    scoreboard = "\n".join([f"{house.capitalize()}: {score}" for house, score in house_points.items()])
    await ctx.send(f"🏆 **House Points** 🏆\n{scoreboard}")

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token found. Did you set DISCORD_TOKEN in .env?")
bot.run(TOKEN)
