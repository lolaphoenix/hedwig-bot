import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

GRINGOTTS_CHANNEL_ID = 1413047433016901743  # #gringotts-bank

# House emojis
house_emojis = {
    "gryffindor": ":gryffindor:",
    "slytherin": ":slytherin:",
    "ravenclaw": ":ravenclaw:",
    "hufflepuff": ":hufflepuff:"
}

# In-memory points store
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
        await ctx.send(f"{house_emojis[house]} {house.capitalize()} now has {house_points[house]} points!")
    else:
        await ctx.send("That house does not exist.")

@bot.command()
async def points(ctx):
    result = "🏆 Current House Points 🏆\n"
    for house, pts in house_points.items():
        result += f"{house_emojis[house]} {house.capitalize()}: {pts}\n"
    await ctx.send(result)

@bot.command()
async def resetpoints(ctx):
    for house in house_points:
        house_points[house] = 0
    await ctx.send("🔄 All house points have been reset to 0!")

@bot.command()
async def removepoints(ctx, house: str, points: int):
    house = house.lower()
    if house in house_points:
        house_points[house] -= points
        await ctx.send(f"{house_emojis[house]} {house.capitalize()} now has {house_points[house]} points!")
    else:
        await ctx.send("That house does not exist.")

# --- Galleon Economy ---

galleons = {}  # Stores user_id : balance

def get_balance(user_id):
    return galleons.get(user_id, 0)

def add_galleons(user_id, amount):
    galleons[user_id] = get_balance(user_id) + amount

def remove_galleons(user_id, amount):
    galleons[user_id] = max(0, get_balance(user_id) - amount)


@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Check your galleon balance."""
    if member is None:
        member = ctx.author
    bal = get_balance(member.id)
    await ctx.send(f"💰 {member.display_name} has **{bal}** galleons.")


@bot.command()
async def givegalleons(ctx, member: discord.Member, amount: int):
    """Give galleons to a user (mod only)."""
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.send("🚫 You don't have permission to give galleons.")
        return
    add_galleons(member.id, amount)
    await ctx.send(f"✨ {member.display_name} received {amount} galleons! "
                   f"They now have {get_balance(member.id)}.")


@bot.command()
async def resetgalleons(ctx):
    """Reset all galleon balances (mod only)."""
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.send("🚫 You don't have permission to reset galleons.")
        return
    galleons.clear()
    await ctx.send("🔄 All galleon balances have been reset.")

import random
from datetime import datetime, timedelta

# Track last daily collection
last_daily = {}  # user_id : datetime

@bot.command()
async def daily(ctx):
    """Collect your daily galleons (once every 24h)."""
    user_id = ctx.author.id
    now = datetime.utcnow()

    if user_id in last_daily and now - last_daily[user_id] < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_daily[user_id])
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes = remainder // 60
        await ctx.send(f"⏳ You already collected your daily galleons. "
                       f"Try again in {hours}h {minutes}m.")
        return

    reward = random.randint(10, 30)  # random pocket money
    add_galleons(user_id, reward)
    last_daily[user_id] = now

    gringotts = bot.get_channel(GRINGOTTS_CHANNEL_ID)
    if gringotts:
        await gringotts.send(f"💰 {ctx.author.display_name} collected their daily allowance "
                             f"and now has {get_balance(user_id)} galleons!")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Send galleons to another user."""
    sender_id = ctx.author.id
    receiver_id = member.id

    if get_balance(sender_id) < amount:
        await ctx.send("🚫 You don’t have enough galleons to do that.")
        return

    remove_galleons(sender_id, amount)
    add_galleons(receiver_id, amount)
    await ctx.send(f"💸 {ctx.author.display_name} paid {amount} galleons to {member.display_name}!")

@bot.command()
async def leaderboard(ctx):
    """Show the richest witches and wizards."""
    if not galleons:
        await ctx.send("No one has any galleons yet!")
        return

    sorted_balances = sorted(galleons.items(), key=lambda x: x[1], reverse=True)[:10]
    result = "🏦 Gringotts Rich List 🏦\n"
    for i, (user_id, bal) in enumerate(sorted_balances, start=1):
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else "Unknown Wizard"
        result += f"{i}. {name} — {bal} galleons\n"

    await ctx.send(result)

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token found. Did you set DISCORD_TOKEN in .env?")

bot.run(TOKEN)
