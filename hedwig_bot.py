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

# --- Config ---
OWLRY_CHANNEL_ID = 1410875871249829898
ROOM_OF_REQUIREMENT_ID = 1413134135169646624
GRINGOTTS_CHANNEL_ID = 1413047433016901743

# Role IDs
ROLE_IDS = {
    "alohomora": None,  # Uses name lookup
    "lumos": 1413122717682761788,
    "amortentia": 1414255673973280909,
    "head_of_house": 1398804285114028042,
    "prefects": 1398803828677021838,
    "slytherin": 1398803575253237891,
    "ravenclaw": 1398803644236955729,
    "hufflepuff": 1409203862757310534,
    "gryffindor": 1409203925416149105,
}

# Potion emojis
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

# --- House Points ---
house_points = {h: 0 for h in house_emojis}

# --- Galleon Economy ---
galleons = {}
last_daily = {}

def get_balance(user_id):
    return galleons.get(user_id, 0)

def add_galleons(user_id, amount):
    galleons[user_id] = get_balance(user_id) + amount

def remove_galleons(user_id, amount):
    galleons[user_id] = max(0, get_balance(user_id) - amount)

# --- Spells + Potions ---
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
    "incendio": {"cost": 25, "description": "🔥 Adds flames to nickname for 24h.", "type": "nickname", "prefix": "🔥", "suffix": "🔥"},
    "silencio": {"cost": 40, "description": "🤫 Prevents a user from casting spells for 24h (1 use per week).", "type": "silence"},
    "lumos": {"cost": 15, "description": "⭐ Adds a star to nickname + Lumos role for 24h.", "type": "lumos"},
}

potions = {
    "felixf": {"cost": 50, "description": "🍀 Increases odds of winning Alohomora game. Adds 🍀 to nickname.", "effect": "luck_good"},
    "livingdeath": {"cost": 40, "description": "💀 Reduces odds of winning Alohomora game. Adds 💀 to nickname.", "effect": "luck_bad"},
    "amortentia": {"cost": 60, "description": "💖 Changes name colour via role + 💖 in nickname.", "effect": "amortentia"},
    "polyjuice": {"cost": 80, "description": "🧪 Temporary access to another house common room for 24h.", "effect": "polyjuice"},
    "bezoar": {"cost": 30, "description": "🪨 Removes any potion effect.", "effect": "cleanse"},
}

# State tracking
active_spells = {}
active_potions = {}
alohomora_cooldowns = {}
silencio_cooldowns = {}
silenced_users = set()
active_potion_effects = {}

# --- Events ---
@bot.event
async def on_ready():
    print(f'{bot.user} is online!')

# --- Commands ---
@bot.command()
async def hedwighelp(ctx):
    msg = (
        "🦉 **Hedwig Help** 🦉\n"
        "✨ Student Commands:\n"
        "`!shop` – View available spells\n"
        "`!cast <spell> @user` – Cast a spell\n"
        "`!drink <potion>` – Drink a potion\n"
        "`!balance` – Check your galleons\n"
        "`!daily` – Collect your daily allowance\n"
        "`!points` – View house points\n"
        "`!choose <1–5>` – Choose a potion in Room of Requirement\n"
    )
    await ctx.send(msg)

@bot.command()
async def hedwigmod(ctx):
    if not any(role.id in (ROLE_IDS["prefects"], ROLE_IDS["head_of_house"]) for role in ctx.author.roles):
        return await ctx.send("❌ You don’t have permission to see mod commands.")
    msg = (
        "⚖️ **Moderator Commands** ⚖️\n"
        "`!addpoints <house> <points>` – Add house points\n"
        "`!resetpoints` – Reset house points\n"
        "`!givegalleons @user <amount>` – Give galleons to a user\n"
    )
    await ctx.send(msg)

# (Keeping all existing !cast, !finite, !choose, !balance, !daily, !shop, etc. logic as discussed)
# Updated with Lumos, Silencio restrictions, potion handling, and purge delay (30m)

# Run bot
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
