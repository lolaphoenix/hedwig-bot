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

# Role IDs (from you)
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
    if os.path.exists(GALLEONS_FILE):
        with open(GALLEONS_FILE, "r") as f:
            galleons = {int(k): int(v) for k, v in json.load(f).items()}
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, "r") as f:
            house_points.update(json.load(f))
    if os.path.exists(EFFECTS_FILE):
        try:
            with open(EFFECTS_FILE, "r") as f:
                effects.update(json.load(f))
        except: pass
    if os.path.exists(LAST_DAILY_FILE):
        with open(LAST_DAILY_FILE, "r") as f:
            raw = json.load(f)
            last_daily = {int(k): datetime.fromisoformat(v) for k, v in raw.items()}
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r") as f:
            reminders.update({int(k): v for k, v in json.load(f).items()})

def save_galleons():
    with open(GALLEONS_FILE, "w") as f:
        json.dump({str(k): v for k, v in galleons.items()}, f, indent=2)

def save_points():
    with open(POINTS_FILE, "w") as f:
        json.dump(house_points, f, indent=2)

def save_effects():
    with open(EFFECTS_FILE, "w") as f:
        json.dump(effects, f, indent=4)

def save_last_daily():
    with open(LAST_DAILY_FILE, "w") as f:
        json.dump({str(k): v.isoformat() for k, v in last_daily.items()}, f, indent=2)

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
        "cost": 50,
        "kind": "role_alohomora",
        "duration": 86400,
        "description": "Access to the Room of Requirement for 24 hours."
    },
    "lumos": {
        "cost": 15,
        "kind": "role_lumos",
        "prefix_unicode": "⭐ ",
        "duration": 86400,
        "description": "Gives Lumos role and star prefix."
    },
    "nox": {
        "cost": 0,
        "kind": "cleanse_lumos",
        "description": "Removes Lumos effect."
    },
    "amortentia": {
        "cost": 100,
        "kind": "role_amortentia",
        "prefix_unicode": "💕 ",
        "duration": 43200,
        "description": "Amortentia role and heart prefix."
    }
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
            active_effects[member.id] = {
                "original_nick": member.display_name,
                "effects": []
            }

    entry = {
        "uid": uid,
        "effect": effect_name,
        "source": source,
        "expires_at": final_expires_at.isoformat() if final_expires_at else None,
        **effect_def,
        "meta": meta or {}
    }

    if effect_def.get("kind") == "cleanse_lumos":
        active_effects[member.id]["effects"] = [e for e in active_effects[member.id]["effects"] if e["effect"] != "lumos"]
    else:
        active_effects[member.id]["effects"].append(entry)

    effects[str(member.id)] = active_effects[member.id]
    save_effects()

    if final_expires_at:
        asyncio.create_task(schedule_expiry(member.id, uid, final_expires_at))

    await update_member_display(member)

async def schedule_expiry(user_id: int, uid: str, expires_at: datetime):
    delta = (expires_at - now_utc()).total_seconds()
    if delta > 0:
        await asyncio.sleep(delta)
    
    member = get_member_from_id(user_id)
    if member:
        await expire_effect(member, uid)

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

    if expired:
        if expired.get("effect") == "alohomora":
            role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role: await safe_remove_role(member, role)
            if current_room_user == member.id:
                current_room_user = None
            active_potions.pop(member.id, None)
            
            chan = bot.get_channel(DUELING_CLUB_ID)
            if chan:
                await chan.send("You hear a soft rumbling inside of the walls...")
        
        if expired.get("kind") == "role_lumos":
            role = member.guild.get_role(ROLE_IDS["lumos"])
            if role: await safe_remove_role(member, role)

    await update_member_display(member)

async def update_member_display(member: discord.Member):
    user_data = active_effects.get(member.id, {"effects": []})
    
    # Update Roles
    for e in user_data["effects"]:
        if e.get("kind") == "role_alohomora":
            role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role: await safe_add_role(member, role)
        if e.get("kind") == "role_lumos":
            role = member.guild.get_role(ROLE_IDS["lumos"])
            if role: await safe_add_role(member, role)

    # Update Nickname
    display_name = user_data.get("original_nick", member.name)
    for e in user_data["effects"]:
        prefix = e.get("prefix_unicode", "")
        display_name = f"{prefix}{display_name}"
    
    await set_nickname(member, display_name)

# -------------------------
# STAFF OVERRIDE: !force alohomora
# -------------------------

@bot.group(name="force", invoke_without_command=True)
async def force_group(ctx):
    """Staff override commands."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("🚫 You do not have permission for force commands.")
    await ctx.send("Usage: `!force alohomora @user` or `!force clear_room`")

@force_group.command(name="alohomora")
async def force_alohomora(ctx, member: discord.Member):
    """Bypasses cooldowns and force-opens the Room of Requirement."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("🚫 Prefects and Heads of House only.")

    global current_room_user, active_potions

    # 1. Clear cooldown error for the target
    if member.id in alohomora_cooldowns:
        del alohomora_cooldowns[member.id]
    
    # 2. Clear room if someone else is inside
    if current_room_user and current_room_user != member.id:
        old_occupant = ctx.guild.get_member(current_room_user)
        if old_occupant:
            data = active_effects.get(old_occupant.id, {"effects": []})
            alo = next((e for e in data["effects"] if e["effect"] == "alohomora"), None)
            if alo: await expire_effect(old_occupant, alo["uid"])

    # 3. Assign new occupant and start potion logic
    current_room_user = member.id
    active_potions[member.id] = {
        "winning": random.randint(1, 5),
        "chosen": False,
        "started_by": member.id
    }

    # 4. Give role and 24h timer
    await apply_effect_to_member(member, "alohomora", source="staff_override")

    await ctx.send(f"🪄 **Staff Override:** {member.mention} has been granted access. Cooldowns reset and potion game initialized.")
    
    room_chan = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if room_chan:
        await room_chan.send(f"🛡️ {member.mention}, the Room of Requirement has opened for you. Choose a potion: `!drink <1-5>`.")

# -------------------------
# BOT COMMANDS
# -------------------------

@bot.command(name="alohomora")
async def alohomora(ctx):
    global current_room_user, active_potions
    if ctx.channel.id != DUELING_CLUB_ID: return

    # Check cooldown
    last_cast = alohomora_cooldowns.get(ctx.author.id)
    if last_cast and (datetime.utcnow() - last_cast) < timedelta(hours=24):
        wait_time = timedelta(hours=24) - (datetime.utcnow() - last_cast)
        hours, remainder = divmod(int(wait_time.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return await ctx.send(f"You're too exhausted to cast that again. Wait {hours}h {minutes}m.")

    if current_room_user is not None:
        return await ctx.send("The room is currently occupied. You hear someone else inside...")

    # Check funds
    cost = EFFECT_LIBRARY["alohomora"]["cost"]
    bal = galleons.get(ctx.author.id, 0)
    if bal < cost:
        return await ctx.send(f"You don't have enough galleons! You need {cost}G.")

    # Deduct and Apply
    galleons[ctx.author.id] = bal - cost
    save_galleons()
    alohomora_cooldowns[ctx.author.id] = datetime.utcnow()

    # Setup room logic
    current_room_user = ctx.author.id
    active_potions[ctx.author.id] = {
        "winning": random.randint(1, 5),
        "chosen": False,
        "started_by": ctx.author.id
    }

    await apply_effect_to_member(ctx.author, "alohomora")
    await ctx.send(f"🪄 {ctx.author.mention} cast **Alohomora**! The hidden door in the wall swings open. (50 Galleons deducted)")

@bot.command(name="drink")
async def drink(ctx, choice: int):
    global current_room_user, active_potions
    if ctx.channel.id != ROOM_OF_REQUIREMENT_ID: return
    
    if current_room_user != ctx.author.id:
        return await ctx.send("You haven't gained access to the room!")
    
    if choice < 1 or choice > 5:
        return await ctx.send("Choose a potion between 1 and 5.")

    game = active_potions.get(ctx.author.id)
    if not game:
        return await ctx.send("The room feels empty... (Try `!force alohomora` if you're stuck)")

    if choice == game["winning"]:
        await ctx.send(f"✨ {POTION_EMOJIS[choice-1]} **Correct!** You've brewed the perfect draught. You feel strengthened.")
    else:
        await ctx.send(f"💨 {POTION_EMOJIS[choice-1]} The potion tastes like swamp water. That wasn't the one.")

@bot.command(name="daily")
async def daily(ctx):
    if ctx.channel.id != GRINGOTTS_CHANNEL_ID: return
    now = datetime.utcnow()
    last = last_daily.get(ctx.author.id)
    
    if last and (now - last) < timedelta(hours=24):
        return await ctx.send("You've already collected your allowance today!")
    
    amount = random.randint(10, 25)
    galleons[ctx.author.id] = galleons.get(ctx.author.id, 0) + amount
    last_daily[ctx.author.id] = now
    save_galleons()
    save_last_daily()
    await ctx.send(f"💰 A goblin hands you **{amount} Galleons**. Come back tomorrow!")

@bot.command(name="bal")
async def bal(ctx):
    amount = galleons.get(ctx.author.id, 0)
    await ctx.send(f"💰 You have **{amount} Galleons** in your vault.")

@bot.command(name="duel")
async def duel(ctx, opponent: discord.Member):
    if ctx.channel.id != DUELING_CLUB_ID: return
    if opponent == ctx.author: return await ctx.send("You can't duel yourself!")
    
    await ctx.send(f"⚔️ {ctx.author.mention} challenges {opponent.mention} to a duel! {opponent.mention}, do you accept? (Type `accept`)")
    
    def check(m): return m.author == opponent and m.content.lower() == "accept" and m.channel == ctx.channel
    try:
        await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        return await ctx.send("The challenge was ignored.")

    winner = random.choice([ctx.author, opponent])
    await ctx.send(f"🪄 Sparks fly! After a fierce exchange, **{winner.mention}** wins the duel!")

# -------------------------
# BOT STARTUP
# -------------------------

@bot.event
async def on_ready():
    load_all_data()
    print(f"Logged in as {bot.user.name}")
    print("Hedwig is ready to deliver.")

# Handle termination gracefully
def signal_handler(sig, frame):
    save_effects()
    save_galleons()
    print("Saving and shutting down...")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)

bot.run(TOKEN)