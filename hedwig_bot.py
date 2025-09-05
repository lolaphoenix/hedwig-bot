import os
import random
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for nickname and role changes

bot = commands.Bot(command_prefix="!", intents=intents)

# Config
OWLRY_CHANNEL_ID = 1410875871249829898  # replace with your #owlry-testing channel ID
ROOM_OF_REQUIREMENT_ID = 1413134135169646624  # replace with your #room-of-requirement channel ID
ALOHOMORA_ROLE = "Alohomora"
GRINGOTTS_CHANNEL_ID = 1413047433016901743  # #gringotts-bank

# House emojis
house_emojis = {
    "gryffindor": ":gryffindor:",
    "slytherin": ":slytherin:",
    "ravenclaw": ":ravenclaw:",
    "hufflepuff": ":hufflepuff:"
}

# --- Utility ---
def get_original_nick(member):
    return active_spells.get(member.id, {}).get("original_nick", member.display_name)

async def schedule_finite(member):
    """Schedule Finite 24 hours after casting a spell."""
    await asyncio.sleep(86400)  # 24h in seconds
    channel = bot.get_channel(OWLRY_CHANNEL_ID)
    if channel:
        await channel.send(f"!finite {member.mention}")

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

# --- Points System ---

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

# --- Spell Shop System ---

spells = {
    "alohomora": {
        "cost": 50,
        "description": "🔑 Grants access to the Room of Requirement.",
        "type": "role",
        "role_name": "Alohomora"
    },
    "aguamenti": {
        "cost": 20,
        "description": "💧 Surrounds target’s nickname with 🌊 for 24 hours.",
        "type": "nickname",
        "prefix": "🌊",
        "suffix": "🌊"
    },
    "confundo": {
        "cost": 25,
        "description": "❓ Adds CONFUNDED before nickname for 24 hours.",
        "type": "nickname",
        "prefix": "❓CONFUNDED - ",
        "suffix": ""
    },
    "diffindo": {
        "cost": 30,
        "description": "✂️ Cuts the last 5 letters off nickname for 24 hours.",
        "type": "truncate",
        "length": 5
    },
    "ebublio": {
        "cost": 20,
        "description": "🫧 Surrounds target’s nickname with bubbles for 24 hours.",
        "type": "nickname",
        "prefix": "🫧",
        "suffix": "🫧"
    },
    "herbifors": {
        "cost": 20,
        "description": "🌸 Surrounds target’s nickname with flowers for 24 hours.",
        "type": "nickname",
        "prefix": "🌸",
        "suffix": "🌸"
    },
    "locomotorwibbly": {
        "cost": 20,
        "description": "🍮 Surrounds target’s nickname with jelly wobble for 24 hours.",
        "type": "nickname",
        "prefix": "🍮",
        "suffix": "🍮"
    },
    "serpensortia": {
        "cost": 20,
        "description": "🐍 Surrounds target’s nickname with snakes for 24 hours.",
        "type": "nickname",
        "prefix": "🐍",
        "suffix": "🐍"
    },
    "tarantallegra": {
        "cost": 20,
        "description": "💃 Surrounds target’s nickname with dancing emojis for 24 hours.",
        "type": "nickname",
        "prefix": "💃",
        "suffix": "💃"
    }
}

# Track active spell effects
active_spells = {}  # {user_id: {"original_nick": str, "spell": str}}

@bot.command()
async def shop(ctx):
    """View available spells."""
    shop_text = "🪄 **Welcome to the Spell Shop!** 🪄\n"
    for spell, data in spells.items():
        shop_text += f"**{spell.capitalize()}** - {data['cost']} galleons\n   {data['description']}\n"
    await ctx.send(shop_text)

# --- Room of Requirement Potion Game ---
active_potions = {}  # {user_id: {"winning": int, "chosen": bool}}

@bot.command()
async def choose(ctx, number: int):
    """Choose one of the 5 potions in the Room of Requirement."""
    if number < 1 or number > 5:
        await ctx.send("🚫 Please choose a number between 1 and 5.")
        return

    user_id = ctx.author.id
    if user_id not in active_potions:
        await ctx.send("❌ You don’t have an active potion challenge. Cast Alohomora first!")
        return

    if active_potions[user_id]["chosen"]:
        await ctx.send("🧪 You’ve already chosen your potion!")
        return

    active_potions[user_id]["chosen"] = True
    winning = active_potions[user_id]["winning"]

    if number == winning:
        add_galleons(user_id, 100)
        await ctx.send(f"🎉 {ctx.author.mention} chose potion {number} and it was the lucky one! "
                       f"You gain **100 galleons**! 💰")
    else:
        await ctx.send(f"💨 {ctx.author.mention} chose potion {number}... but alas, nothing happens. "
                       f"Better luck next time!")

@bot.command()
async def cast(ctx, spell: str, member: discord.Member):
    """Cast a spell on someone if you can afford it."""
    spell = spell.lower()
    if spell not in spells:
        await ctx.send("❌ That spell doesn’t exist. Check the shop with `!shop`.")
        return

    cost = spells[spell]["cost"]
    if get_balance(ctx.author.id) < cost:
        await ctx.send("💸 You don’t have enough galleons to cast that spell!")
        return

    # Deduct cost
    remove_galleons(ctx.author.id, cost)

    # Save original nickname
    active_spells[member.id] = {"original_nick": member.display_name, "spell": spell}

    data = spells[spell]
    if data["type"] == "role":
        role = discord.utils.get(ctx.guild.roles, name=data["role_name"])
        if not role:
            await ctx.send(f"⚠️ The role `{data['role_name']}` does not exist. Please ask an admin to create it.")
            return
        await member.add_roles(role)
        await ctx.send(f"✨ {ctx.author.display_name} cast **{spell.capitalize()}** on {member.display_name}!")

        if spell == "alohomora":
            # Start potion game
            active_potions[member.id] = {"winning": random.randint(1, 5), "chosen": False}
            room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
            if room:
                await room.send(
                    f"🔮 Welcome {member.mention} to the Room of Requirement!\n"
                    f"Choose wisely… pick a potion with `!choose 1–5`\n"
                    f":potion1: :potion2: :potion3: :potion4: :potion5:"
                )

    elif data["type"] == "nickname":
        new_name = f"{data['prefix']}{member.display_name}{data['suffix']}"
        await member.edit(nick=new_name)
    elif data["type"] == "truncate":
        new_name = member.display_name[:-data["length"]] if len(member.display_name) > data["length"] else member.display_name
        await member.edit(nick=new_name)

    asyncio.create_task(schedule_finite(member))

@bot.command()
async def finite(ctx, member: discord.Member):
    """Revert user back to original nickname and remove Alohomora role."""
    if member.id in active_spells:
        orig = active_spells[member.id]["original_nick"]
        await member.edit(nick=orig)
        del active_spells[member.id]
        await ctx.send(f"✨ Finite! {member.display_name} has been restored.")

    role = discord.utils.get(ctx.guild.roles, name="Alohomora")
    if role and role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"🔒 The Room of Requirement is closed for {member.display_name}.")

@bot.command()
async def trigger_game(ctx):
    """Admin/testing command to trigger the potion game manually."""
    user_id = ctx.author.id
    active_potions[user_id] = {"winning": random.randint(1, 5), "chosen": False}

    await ctx.send(
        f"🧪 Testing potion game for {ctx.author.mention}!\n"
        f"Choose wisely with `!choose 1–5`\n"
        f":potion1: :potion2: :potion3: :potion4: :potion5:"
    )

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token found. Did you set DISCORD_TOKEN in .env?")

bot.run(TOKEN)
