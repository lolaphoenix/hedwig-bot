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
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Config
OWLRY_CHANNEL_ID = 1410875871249829898
ROOM_OF_REQUIREMENT_ID = 1413134135169646624
ALOHOMORA_ROLE = "Alohomora"
GRINGOTTS_CHANNEL_ID = 1413047433016901743
ALLOWED_ROLES = ["Prefects", "Head of House"]  # roles allowed to give galleons

# Custom potion emojis
POTION_EMOJIS = [
    "<:potion1:1413860131073953856>",
    "<:potion2:1413860185801490463>",
    "<:potion3:1413860235382231202>",
    "<:potion4:1413860291124531220>",
    "<:potion5:1413860345055019201>",
]

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

async def schedule_finite(member, spell):
    """Schedule Finite 24h after casting a spell."""
    await asyncio.sleep(86400)
    channel = bot.get_channel(OWLRY_CHANNEL_ID)
    if channel:
        await channel.send(f"!finite {member.mention} {spell}")

# In-memory house points
house_points = {h: 0 for h in house_emojis}

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')

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
    await ctx.send("🔄 All house points have been reset!")

# --- Galleon Economy ---
galleons = {}
last_daily = {}

def get_balance(user_id):
    return galleons.get(user_id, 0)

def add_galleons(user_id, amount):
    galleons[user_id] = get_balance(user_id) + amount

def remove_galleons(user_id, amount):
    galleons[user_id] = max(0, get_balance(user_id) - amount)

@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"💰 {member.display_name} has **{get_balance(member.id)}** galleons.")

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    now = datetime.utcnow()
    if user_id in last_daily and now - last_daily[user_id] < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_daily[user_id])
        hrs, rem = divmod(remaining.seconds, 3600)
        mins = rem // 60
        await ctx.send(f"⏳ Try again in {hrs}h {mins}m.")
        return
    reward = random.randint(10, 30)
    add_galleons(user_id, reward)
    last_daily[user_id] = now
    gringotts = bot.get_channel(GRINGOTTS_CHANNEL_ID)
    if gringotts:
        await gringotts.send(f"💰 {ctx.author.display_name} collected daily allowance "
                             f"and now has {get_balance(user_id)} galleons!")

@bot.command()
async def givegalleons(ctx, member: discord.Member, amount: int):
    """Give galleons to a user (restricted to Prefects & Head of House)."""
    if not any(r.name in ALLOWED_ROLES for r in ctx.author.roles):
        return await ctx.send("🚫 You don't have permission to give galleons.")

    add_galleons(member.id, amount)
    await ctx.send(f"✨ {member.display_name} received {amount} galleons! "
                   f"They now have {get_balance(member.id)}.")

@bot.command()
async def resetgalleons(ctx):
    """Reset all galleon balances (restricted)."""
    if not any(r.name in ALLOWED_ROLES for r in ctx.author.roles):
        return await ctx.send("🚫 You don't have permission to reset galleons.")

    galleons.clear()
    await ctx.send("🔄 All galleon balances have been reset!")

# --- Spell Shop ---
spells = {
    "alohomora": {"cost": 50, "description": "🔑 Grants access to the Room of Requirement.", "type": "role"},
    "aguamenti": {"cost": 20, "description": "💧 Adds 🌊 around nickname for 24h.", "type": "nickname", "prefix": "🌊", "suffix": "🌊"},
    "confundo": {"cost": 25, "description": "❓ Adds CONFUNDED before nickname for 24h.", "type": "nickname", "prefix": "❓CONFUNDED - ", "suffix": ""},
    "diffindo": {"cost": 30, "description": "✂️ Cuts last 5 letters for 24h.", "type": "truncate", "length": 5},
    "ebublio": {"cost": 20, "description": "🫧 Adds bubbles around nickname for 24h.", "type": "nickname", "prefix": "🫧", "suffix": "🫧"},
    "herbifors": {"cost": 20, "description": "🌸 Adds flowers around nickname for 24h.", "type": "nickname", "prefix": "🌸", "suffix": "🌸"},
    "locomotorwibbly": {"cost": 20, "description": "🍮 Adds jelly wobble around nickname for 24h.", "type": "nickname", "prefix": "🍮", "suffix": "🍮"},
    "serpensortia": {"cost": 20, "description": "🐍 Adds snakes around nickname for 24h.", "type": "nickname", "prefix": "🐍", "suffix": "🐍"},
    "tarantallegra": {"cost": 20, "description": "💃 Adds dancers around nickname for 24h.", "type": "nickname", "prefix": "💃", "suffix": "💃"},
}

active_spells = {}  # {user_id: {"original_nick": str, "spells": [list of spell keys]}}
alohomora_cooldowns = {}  # user_id : datetime

@bot.command()
async def shop(ctx):
    msg = "🪄 **Spell Shop** 🪄\n"
    for s, d in spells.items():
        msg += f"**{s.capitalize()}** - {d['cost']} galleons\n   {d['description']}\n"
    await ctx.send(msg)

@bot.command()
async def cast(ctx, spell: str, member: discord.Member):
    spell = spell.lower()
    if spell not in spells:
        return await ctx.send("❌ That spell doesn’t exist.")

    # Alohomora cooldown
    if spell == "alohomora":
        now = datetime.utcnow()
        if member.id in alohomora_cooldowns and now - alohomora_cooldowns[member.id] < timedelta(hours=24):
            return await ctx.send("⏳ Alohomora can only be cast on this user once every 24h.")
        alohomora_cooldowns[member.id] = now

    cost = spells[spell]["cost"]
    if get_balance(ctx.author.id) < cost:
        return await ctx.send("💸 Not enough galleons!")

    remove_galleons(ctx.author.id, cost)
    if member.id not in active_spells:
        active_spells[member.id] = {"original_nick": member.display_name, "spells": []}
    active_spells[member.id]["spells"].append(spell)

    data = spells[spell]
    if data["type"] == "role":
        role = discord.utils.get(ctx.guild.roles, name=ALOHOMORA_ROLE)
        if role:
            await member.add_roles(role)
        # Potion game
        active_potions[member.id] = {"winning": random.randint(1, 5), "chosen": False}
        room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
        if room:
            await room.send(
                f"🔮 Welcome {member.mention}!\nPick a potion with `!choose 1–5`\n" +
                " ".join(POTION_EMOJIS)
            )
    elif data["type"] == "nickname":
        await member.edit(nick=f"{data['prefix']}{member.display_name}{data['suffix']}")
    elif data["type"] == "truncate":
        await member.edit(nick=member.display_name[:-data["length"]])

    await ctx.send(f"✨ {ctx.author.display_name} cast **{spell.capitalize()}** on {member.display_name}!")
    asyncio.create_task(schedule_finite(member, spell))

@bot.command()
async def finite(ctx, member: discord.Member, spell: str = None):
    """Reverts the last or a specific spell from a user."""
    if member.id not in active_spells:
        return await ctx.send("No active spells on this user.")

    spells_list = active_spells[member.id]["spells"]
    if spell and spell.lower() in spells_list:
        spells_list.remove(spell.lower())
    elif spells_list:
        spells_list.pop()

    if not spells_list:  # restore original nickname
        orig = active_spells[member.id]["original_nick"]
        await member.edit(nick=orig)
        del active_spells[member.id]
        await ctx.send(f"✨ {member.display_name} fully restored.")
    else:
        await ctx.send(f"✨ Removed one spell from {member.display_name}. Still enchanted.")

# --- Room of Requirement Game ---
active_potions = {}

@bot.command()
async def choose(ctx, number: int):
    if number < 1 or number > 5:
        return await ctx.send("🚫 Pick 1–5.")

    user_id = ctx.author.id
    if user_id not in active_potions:
        return await ctx.send("❌ No active potion challenge. Cast Alohomora first.")

    if active_potions[user_id]["chosen"]:
        return await ctx.send("🧪 You already chose.")

    active_potions[user_id]["chosen"] = True
    winning = active_potions[user_id]["winning"]

    if number == winning:
        add_galleons(user_id, 100)
        await ctx.send(f"🎉 {ctx.author.mention} picked potion {number} and won **100 galleons**!")
    else:
        await ctx.send(f"💨 {ctx.author.mention} picked potion {number} but nothing happened.")

    # Remove Alohomora role + clear room
    member = ctx.author
    role = discord.utils.get(ctx.guild.roles, name=ALOHOMORA_ROLE)
    if role and role in member.roles:
        await member.remove_roles(role)
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if room:
        await room.purge(limit=100)

@bot.command()
@commands.has_role("Prefects")  # only Prefects can trigger test
async def trigger_game(ctx, member: discord.Member = None):
    """Testing only: Start the Room of Requirement potion game manually."""
    member = member or ctx.author
    active_potions[member.id] = {"winning": random.randint(1, 5), "chosen": False}
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if room:
        await room.send(
            f"🔮 Welcome {member.mention} (test mode)!\nPick a potion with `!choose 1–5`\n" +
            " ".join(POTION_EMOJIS)
        )

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
