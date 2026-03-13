# hedwig_bot.py
import os
import random
import asyncio
import uuid
import discord
import json
import time
import signal
import datetime as dt 
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta

# -------------------------
# CONFIG / SETUP
# -------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Channel IDs
OWLRY_CHANNEL_ID = 1410875871249829898
ROOM_OF_REQUIREMENT_ID = 1413134135169646624
GRINGOTTS_CHANNEL_ID = 1413047433016901743
DUELING_CLUB_ID = 1417131924132069416

# Role IDs
ROLE_IDS = {
    "lumos": 1413122717682761788,
    "amortentia": 1414255673973280909,
    "head_of_house": 1398804285114028042,
    "prefects": 1398803828677021838,
    "slytherin": 1398803575253237891,
    "ravenclaw": 1398803644236955729,
    "hufflepuff": 1409203862757310534,
    "gryffindor": 1409203925416149105,
    "alohomora": 1413134328690638858, 
}
ALOHOMORA_ROLE_NAME = "Alohomora"

# Potion emojis
POTION_EMOJIS = [
    "<:potion1:1413860131073953856>",
    "<:potion2:1413860185801490463>",
    "<:potion3:1413860235382231202>",
    "<:potion4:1413860291124531220>",
    "<:potion5:1413860345055019201>",
]

house_emojis = {
    "gryffindor": "<:gryffindor:1398846272114524300>",
    "slytherin": "<:slytherin:1398846083463122984>",
    "ravenclaw": "<:ravenclaw:1398846388430835752>",
    "hufflepuff": "<:hufflepuff:1398846494844387379>",
}

# -------------------------
# PERSISTENCE SETUP
# -------------------------
try:
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
except NameError:
    DATA_DIR = os.path.join(os.getcwd(), "data")

os.makedirs(DATA_DIR, exist_ok=True)
GALLEONS_FILE = os.path.join(DATA_DIR, "galleons.json")
POINTS_FILE = os.path.join(DATA_DIR, "house_points.json")
EFFECTS_FILE = "effects.json"
LAST_DAILY_FILE = os.path.join(DATA_DIR, "last_daily.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")

# Global State
galleons = {}
house_points = {h: 0 for h in house_emojis}
last_daily = {}
active_effects = {}
effects = {}
active_potions = {}
current_room_user = None
alohomora_cooldowns = {}
reminders = {}
reminder_tasks = {}

# -------------------------
# PERSISTENCE FUNCTIONS
# -------------------------

def load_all_data():
    global galleons, house_points, last_daily, effects, reminders
    # Galleons
    if os.path.exists(GALLEONS_FILE):
        with open(GALLEONS_FILE, "r") as f:
            galleons = {int(k): int(v) for k, v in json.load(f).items()}
    # House Points
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, "r") as f:
            house_points.update(json.load(f))
    # Effects
    if os.path.exists(EFFECTS_FILE):
        with open(EFFECTS_FILE, "r") as f:
            effects.update(json.load(f))
    # Last Daily
    if os.path.exists(LAST_DAILY_FILE):
        with open(LAST_DAILY_FILE, "r") as f:
            last_daily = {int(k): datetime.fromisoformat(v) for k, v in json.load(f).items()}
    # Reminders
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r") as f:
            reminders.update({int(k): v for k, v in json.load(f).items()})

def save_galleons():
    with open(GALLEONS_FILE, "w") as f:
        json.dump({str(k): v for k, v in galleons.items()}, f, indent=2)

def save_effects():
    with open(EFFECTS_FILE, "w") as f:
        json.dump(effects, f, indent=4)

def save_reminders():
    with open(REMINDERS_FILE, "w") as f:
        json.dump({str(k): v for k, v in reminders.items()}, f, indent=2)

# -------------------------
# HELPERS
# -------------------------
def now_utc():
    return datetime.utcnow()

def is_staff_allowed(member: discord.Member) -> bool:
    allowed_ids = {ROLE_IDS["prefects"], ROLE_IDS["head_of_house"]}
    return any(r.id in allowed_ids for r in member.roles)

def get_member_from_id(user_id: int):
    for guild in bot.guilds:
        m = guild.get_member(user_id)
        if m: return m
    return None

async def safe_add_role(member: discord.Member, role: discord.Role):
    try: await member.add_roles(role)
    except: pass

async def safe_remove_role(member: discord.Member, role: discord.Role):
    try: await member.remove_roles(role)
    except: pass

async def set_nickname(member: discord.Member, new_nick: str):
    if member.id == member.guild.owner_id: return
    try:
        if new_nick and len(new_nick) > 32: new_nick = new_nick[:32]
        await member.edit(nick=new_nick)
    except: pass

# -------------------------
# EFFECT LIBRARIES
# -------------------------

EFFECT_LIBRARY = {
    "alohomora": {
        "cost": 50, "kind": "role_alohomora", "duration": 86400,
        "description": "Access to the Room of Requirement."
    },
    "lumos": {
        "cost": 15, "kind": "role_lumos", "prefix_unicode": "⭐", "duration": 86400,
        "description": "Gives Lumos role and star prefix."
    }
    # Add other spells here as needed
}

# -------------------------
# CORE LOGIC: APPLY / EXPIRE
# -------------------------

async def apply_effect_to_member(member: discord.Member, effect_name: str, source: str = "spell", meta: dict = None, expires_at: datetime = None):
    effect_def = EFFECT_LIBRARY.get(effect_name)
    if not effect_def: return

    final_expires_at = expires_at
    if not final_expires_at and "duration" in effect_def:
        final_expires_at = now_utc() + timedelta(seconds=effect_def["duration"])

    uid = f"{effect_name}_{int(time.time())}"

    if member.id not in active_effects:
        if str(member.id) in effects:
            active_effects[member.id] = effects[str(member.id)]
        else:
            active_effects[member.id] = {"original_nick": member.display_name, "effects": []}

    entry = {
        "uid": uid, "effect": effect_name, "source": source,
        "expires_at": final_expires_at.isoformat() if final_expires_at else None,
        **effect_def, "meta": meta or {}
    }

    active_effects[member.id]["effects"].append(entry)
    effects[str(member.id)] = active_effects[member.id]
    save_effects()

    if final_expires_at:
        asyncio.create_task(schedule_expiry(member.id, uid, final_expires_at))

    await update_member_display(member)

async def schedule_expiry(user_id: int, uid: str, expires_at: datetime):
    delta = (expires_at - now_utc()).total_seconds()
    if delta > 0: await asyncio.sleep(delta)
    member = get_member_from_id(user_id)
    if member: await expire_effect(member, uid)

async def expire_effect(member: discord.Member, uid: str):
    global current_room_user, active_potions
    if member.id not in active_effects: return

    expired = next((e for e in active_effects[member.id]["effects"] if e["uid"] == uid), None)
    active_effects[member.id]["effects"] = [e for e in active_effects[member.id]["effects"] if e["uid"] != uid]

    if not active_effects[member.id]["effects"]:
        active_effects.pop(member.id)
        effects.pop(str(member.id), None)
    else:
        effects[str(member.id)] = active_effects[member.id]
    save_effects()

    if expired and expired.get("effect") == "alohomora":
        role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
        if role: await safe_remove_role(member, role)
        if current_room_user == member.id: current_room_user = None
        active_potions.pop(member.id, None)
        
        dueling_club = bot.get_channel(DUELING_CLUB_ID)
        if dueling_club: await dueling_club.send("You hear a soft rumbling inside of the walls...")

    await update_member_display(member)

async def update_member_display(member: discord.Member):
    user_data = active_effects.get(member.id, {"effects": []})
    
    # Handle Roles
    for e in user_data["effects"]:
        if e.get("kind") == "role_alohomora":
            role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role: await safe_add_role(member, role)
        if e.get("kind") == "role_lumos":
            role = member.guild.get_role(ROLE_IDS["lumos"])
            if role: await safe_add_role(member, role)

    # Handle Nickname
    display_name = user_data.get("original_nick", member.name)
    for e in user_data["effects"]:
        prefix = e.get("prefix_unicode", "")
        display_name = f"{prefix}{display_name}"
    
    await set_nickname(member, display_name)

# -------------------------
# STAFF OVERRIDE COMMAND
# -------------------------

@bot.group(name="force", invoke_without_command=True)
async def force(ctx):
    """Staff override commands."""
    if not is_staff_allowed(ctx.author): return
    await ctx.send("❓ Use `!force alohomora @user` to open the room.")

@force.command(name="alohomora")
async def force_alohomora(ctx, member: discord.Member):
    """Bypasses cooldowns and force-opens the Room of Requirement."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("🚫 You do not have permission for this spell.")

    global current_room_user, active_potions

    # 1. Clear the 24-hour cooldown for this specific user
    if member.id in alohomora_cooldowns:
        del alohomora_cooldowns[member.id]
    
    # 2. Clear room if someone else is in there
    if current_room_user and current_room_user != member.id:
        old_occupant = ctx.guild.get_member(current_room_user)
        if old_occupant:
            # Find and expire their alohomora effect
            data = active_effects.get(old_occupant.id, {"effects": []})
            alo = next((e for e in data["effects"] if e["effect"] == "alohomora"), None)
            if alo: await expire_effect(old_occupant, alo["uid"])

    # 3. Set occupant and INITIALIZE GAME (prevents "Empty Room" bug)
    current_room_user = member.id
    active_potions[member.id] = {
        "winning": random.randint(1, 5),
        "chosen": False,
        "started_by": member.id
    }

    # 4. Apply Effect (24h)
    await apply_effect_to_member(member, "alohomora", source="staff_override")

    await ctx.send(f"🪄 **Staff Override:** The Room of Requirement has opened for {member.mention}.\n"
                   f"Cooldowns cleared and potion game initialized.")
    
    room_chan = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if room_chan:
        await room_chan.send(f"🛡️ {member.mention}, the Room is ready. Use `!drink <1-5>`.")

# -------------------------
# STANDBY COMMANDS
# -------------------------

@bot.command(name="drink")
async def drink(ctx, choice: int):
    global current_room_user, active_potions
    if ctx.channel.id != ROOM_OF_REQUIREMENT_ID: return
    if current_room_user != ctx.author.id:
        return await ctx.send("You haven't gained access to the room yet!")
    
    game = active_potions.get(ctx.author.id)
    if not game:
        return await ctx.send("The room feels strangely empty. (Staff may need to use `!force alohomora`)")
    
    if choice == game["winning"]:
        await ctx.send(f"✨ **Correct!** You've brewed the potion perfectly.")
        # Logic for rewards would go here
    else:
        await ctx.send(f"💨 The potion fizzles out. Try again!")

# -------------------------
# BOT STARTUP
# -------------------------

@bot.event
async def on_ready():
    load_all_data()
    print(f"Logged in as {bot.user.name}")

bot.run(TOKEN)