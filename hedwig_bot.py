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
# New code to ensure the bot can always find its .env file
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BOT_DIR, '.env'))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# GLOBAL VARIABLES
# -------------------------
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
}
ALOHOMORA_ROLE_NAME = "Alohomora"

# Emojis and Mappings
POTION_EMOJIS = [
    "<:potion1:1413860131073953856>",
    "<:potion2:1413860185801490463>",
    "<:potion3:1413860235382231202>",
    "<:potion4:1413860291124531220>",
    "<:potion5:1413680696985442334>",
]
house_emojis = {
    "gryffindor": "<:gryffindor:1398846272114524300>",
    "slytherin": "<:slytherin:1398846083463122984>",
    "ravenclaw": "<:ravenclaw:1398846388430835752>",
    "hufflepuff": "<:hufflepuff:1409203862757310534>",
}
effect_emojis = {
    "tarantallegra": "<:tarantallegra:1415595049411936296>",
    "serpensortia": "<:serpensortia:1415595048124289075>",
    "lumos": "<:lumos:1415595044357931100>",
    "incendio": "<:incendio:1415595041191235718>",
    "herbifors": "<:herbifors:1415595039882481674>",
    "ebublio": "<:ebublio:1415595038397693982>",
    "diffindo": "<:diffindo:1415595036250214500>",
    "confundo": "<:confundo:1415595034769625199>",
    "alohomora": "<:alohomora:1415595033410666629>",
    "aguamenti": "<:aguamenti:1415595031644999742>",
    "amortentia": "<:amortentia:1414255673973280909>",
    "bezoar": "<:bezoar:1415594792217350255>",
    "felixfelicis": "<:felixfelicis:1413679761036673186>",
    "draughtlivingdeath": "<:draughtoflivingdeath:1413679622041894985>",
    "polyjuice": "<:polyjuice:1413679815520944158>",
    "finite": "✂️"
}
effect_unicode = {
    "tarantallegra": "💃",
    "serpensortia": "🐍",
    "lumos": "✨",
    "incendio": "🔥",
    "herbifors": "🌿",
    "ebublio": "🫧",
    "diffindo": "✂️",
    "confundo": "🌀",
    "alohomora": "🗝️",
    "aguamenti": "💧",
    "amortentia": "💖",
    "bezoar": "💊",
    "felixfelicis": "🍀",
    "draughtlivingdeath": "💀",
    "polyjuice": "🧪",
    "finite": "✂️"
}

# In-memory State
galleons = {}
house_points = {h: 0 for h in house_emojis}
effects = {}
active_effects = {}
active_duels = {}
duel_cooldowns = {}
last_daily = {}
active_potions = {}
alohomora_cooldowns = {}

# -------------------------
# PERSISTENCE: data files
# -------------------------
try:
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
except NameError:
    DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

GALLEONS_FILE = os.path.join(DATA_DIR, "galleons.json")
POINTS_FILE = os.path.join(DATA_DIR, "house_points.json")
EFFECTS_FILE = os.path.join(DATA_DIR, "effects.json")
DUEL_COOLDOWNS_FILE = os.path.join(DATA_DIR, "duel_cooldowns.json")

# -------------------------
# PERSISTENCE FUNCTIONS
# -------------------------
# These functions must be defined *after* the file variables above
# so they can be referenced without a NameError.

# --- galleons persistence ---
def load_galleons():
    global galleons
    try:
        if os.path.exists(GALLEONS_FILE):
            with open(GALLEONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # JSON keys are strings — convert to ints
            galleons = {int(k): int(v) for k, v in raw.items()}
            print(f"[Hedwig] loaded {len(galleons)} galleon accounts from {GALLEONS_FILE}")
        else:
            galleons = {}
            save_galleons()
            print(f"[Hedwig] created new galleons file at {GALLEONS_FILE}")
    except Exception as e:
        print("[Hedwig] Failed to load galleons:", e)
        galleons = {}

def save_galleons():
    try:
        tmp = GALLEONS_FILE + ".tmp"
        serializable = {str(k): v for k, v in galleons.items()}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
        os.replace(tmp, GALLEONS_FILE)
    except Exception as e:
        print("[Hedwig] Failed to save galleons:", e)

# --- house points persistence ---
def load_house_points():
    global house_points
    try:
        if os.path.exists(POINTS_FILE):
            with open(POINTS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # ensure we only keep known houses and integers
            for h in house_points:
                if h in raw:
                    house_points[h] = int(raw[h])
            print(f"[Hedwig] loaded house points from {POINTS_FILE}")
        else:
            save_house_points()
            print(f"[Hedwig] created new house points file at {POINTS_FILE}")
    except Exception as e:
        print("[Hedwig] Failed to load house points:", e)

def save_house_points():
    try:
        tmp = POINTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(house_points, f, indent=2)
        os.replace(tmp, POINTS_FILE)
    except Exception as e:
        print("[Hedwig] Failed to save house points:", e)

def load_effects():
    global effects
    try:
        with open(EFFECTS_FILE, "r") as f:
            effects = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        effects = {}

def save_effects():
    with open(EFFECTS_FILE, "w") as f:
        json.dump(effects, f, indent=4)

def load_duel_cooldowns():
    global duel_cooldowns
    try:
        if os.path.exists(DUEL_COOLDOWNS_FILE):
            with open(DUEL_COOLDOWNS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Convert string keys back to int and isoformat back to datetime
            duel_cooldowns = {int(k): datetime.fromisoformat(v) for k, v in raw.items()}
            print(f"[Hedwig] loaded {len(duel_cooldowns)} duel cooldowns.")
        else:
            duel_cooldowns = {}
            save_duel_cooldowns()
            print(f"[Hedwig] created new duel cooldowns file.")
    except Exception as e:
        print(f"[Hedwig] Failed to load duel cooldowns: {e}")
        duel_cooldowns = {}

def save_duel_cooldowns():
    try:
        tmp = DUEL_COOLDOWNS_FILE + ".tmp"
        # Convert datetime objects to ISO format strings for JSON
        serializable = {str(k): v.isoformat() for k, v in duel_cooldowns.items()}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
        os.replace(tmp, DUEL_COOLDOWNS_FILE)
    except Exception as e:
        print(f"[Hedwig] Failed to save duel cooldowns: {e}")

# -------------------------
# STATE (OTHER IN-MEMORY)
# -------------------------
last_daily = {}          # user_id -> datetime
active_effects = {}      # user_id -> {"original_nick": str, "effects": [ ... ]}
active_potions = {}      # user_id -> {"winning": int, "chosen": bool, "started_by": id}

alohomora_cooldowns = {} # target_user_id -> datetime


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
        if m:
            return m
    return None

async def safe_add_role(member: discord.Member, role: discord.Role):
    try:
        await member.add_roles(role)
    except discord.Forbidden:
        print(f"Missing permissions to add role {role} to {member}.")
    except Exception as e:
        print("Error adding role:", e)

async def safe_remove_role(member: discord.Member, role: discord.Role):
    try:
        await member.remove_roles(role)
    except discord.Forbidden:
        print(f"Missing permissions to remove role {role} from {member}.")
    except Exception as e:
        print("Error removing role:", e)

async def set_nickname(member: discord.Member, nickname: str):
    try:
        await member.edit(nick=nickname)
    except discord.Forbidden:
        print(f"Missing Manage Nicknames for {member}.")
    except Exception as e:
        print("Error setting nickname:", e)

def get_balance(user_id: int) -> int:
    return galleons.get(int(user_id), 0)

def add_galleons_local(user_id: int, amount: int):
    user_id = int(user_id)
    galleons[user_id] = get_balance(user_id) + int(amount)
    save_galleons()

def remove_galleons_local(user_id: int, amount: int):
    user_id = int(user_id)
    galleons[user_id] = max(0, get_balance(user_id) - int(amount))
    save_galleons()

def make_effect_uid() -> str:
    return uuid.uuid4().hex

def get_user_house(member: discord.Member):
    for name in ("gryffindor", "slytherin", "ravenclaw", "hufflepuff"):
        rid = ROLE_IDS.get(name)
        if rid and any(r.id == rid for r in member.roles):
            return name
    return None

# -------------------------
# LIBRARIES
# -------------------------

EFFECT_LIBRARY = {
    "aguamenti": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:aguamenti:1415595031644999742>", "prefix_unicode": "🌊",
        "suffix": "<:aguamenti:1415595031644999742>", "suffix_unicode": "🌊",
        "description": "Surrounds the target's nickname with water."
    },
    "confundo": {
        "cost": 25, "kind": "nickname",
        "prefix": "<:confundo:1415595034769625199>", "prefix_unicode": "❓CONFUNDED - ",
        "suffix": "", "suffix_unicode": "❓",
        "description": "Prefixes CONFUNDED to the target's nickname."
    },
    "diffindo": {
        "cost": 30, "kind": "truncate",
        "length": 5,
        "description": "Removes the last 5 characters of the target's nickname."
    },
    "ebublio": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:ebublio:1415595038397693982>", "prefix_unicode": "🫧",
        "suffix": "<:ebublio:1415595038397693982>", "suffix_unicode": "🫧",
        "description": "Surrounds the target's nickname with bubbles."
    },
    "herbifors": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:herbifors:1415595039882481674>", "prefix_unicode": "🌸",
        "suffix": "<:herbifors:1415595039882481674>", "suffix_unicode": "🌸",
        "description": "Gives the target a floral nickname."
    },
    "serpensortia": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:serpensortia:1415595048124289075>", "prefix_unicode": "🐍",
        "suffix": "<:serpensortia:1415595048124289075>", "suffix_unicode": "🐍",
        "description": "Surrounds the target's nickname with snake emojis."
    },
    "tarantallegra": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:tarantallegra:1415595049411936296>", "prefix_unicode": "💃",
        "suffix": "<:tarantallegra:1415595049411936296>", "suffix_unicode": "💃",
        "description": "Adds dancing emojis around the target's nickname."
    },
    "incendio": {
        "cost": 25, "kind": "nickname",
        "prefix": "<:incendio:1415595041191235718>", "prefix_unicode": "🔥",
        "suffix": "<:incendio:1415595041191235718>", "suffix_unicode": "🔥",
        "description": "Adds flames to the target's nickname."
    },
    "alohomora": {
        "cost": 50, "kind": "role_alohomora", "duration": 86400, "description": "Grants access to the Room of Requirement for 24 hours and starts the potion game."
    },
    "lumos": {
        "cost": 15, "kind": "role_lumos", "prefix": "<:lumos:1415595044357931100>", "prefix_unicode": "⭐", "suffix_unicode": "⭐", "description": "Gives the Lumos role and a star prefix to the nickname."
    },
    "finite": {
        "cost": 10, "kind": "finite", "duration": 0, "description": "Finite: removes the most recent spell/potion from a user when cast."
    },
}
POTION_LIBRARY = {
    "felixfelicis": {
        "emoji": "<:felixfelicis:1413679761036673186>",
        "cost": 60,
        "kind": "potion_luck_good",
        "prefix": "<:felixfelicis:1414255673973280909>",
        "prefix_unicode": "🍀",
        "duration": 3600,
        "description": "Good luck potion.",
    },
    "draughtoflivingdeath": {
        "emoji": "<:draughtoflivingdeath:1413679622041894985>",
        "cost": 60,
        "kind": "potion_luck_bad",
        "prefix": "<:draughtoflivingdeath:1413679622041894985>",
        "prefix_unicode": "💀",
        "duration": 3600,
        "description": "Bad luck potion.",
    },
    "polyjuice": {
        "emoji": "<:polyjuice:1413679815520944158>",
        "cost": 60,
        "kind": "potion_house_change",
        "prefix": "<:polyjuice:1413679815520944158>",
        "prefix_unicode": "🧪",
        "description": "Changes the target's house.",
        "duration": 3600,
    },
    "amortentia": {
        "emoji": "<:amortentia:1414255673973280909>",
        "cost": 60,
        "kind": "potion_staff_allow",
        "prefix": "<:amortentia:1414255673973280909>",
        "prefix_unicode": "💖",
        "description": "Allows non-staff members to use staff commands for one hour.",
        "duration": 3600,
    },
}

# -------------------------
# BOT COMMANDS
# -------------------------

@bot.event
async def on_ready():
    """Bot initialization when connected to Discord."""
    print("--------------------")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("--------------------")
    # A single guild is likely
    if bot.guilds:
        print(f"Connected to guild: {bot.guilds[0].name}")
    else:
        print("Not connected to any guilds!")
    
    # Load persistence files
    load_galleons()
    load_house_points()
    load_effects()
    load_duel_cooldowns()
    
    # Start cleanup task
    if not cleanup_effects.is_running():
        cleanup_effects.start()
    
    # Restore roles and nicknames for any lingering effects
    print("[Hedwig] Checking for active effects on members...")
    for uid, data in list(effects.items()):
        member = get_member_from_id(int(uid))
        if not member:
            print(f"Member with ID {uid} not found. Skipping effect restoration.")
            continue

        try:
            active_effects[member.id] = data
            for e in data["effects"]:
                if "role_alohomora" in e["kind"]:
                    role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
                    if role:
                        await safe_add_role(member, role)
                
                if "role_lumos" in e["kind"]:
                    role = discord.utils.get(member.guild.roles, id=ROLE_IDS["lumos"])
                    if role:
                        await safe_add_role(member, role)
                
                # Restore nickname prefix if it exists
                if data["original_nick"] and "prefix_unicode" in EFFECT_LIBRARY.get(e["name"], {}):
                    await set_nickname(member, f"{EFFECT_LIBRARY[e['name']]['prefix_unicode']} {data['original_nick']}")
        except Exception as err:
            print(f"Error restoring effect for {member.display_name}: {err}")

        if active_effects[member.id]["effects"]:
            new_effects[uid] = active_effects[member.id]

    # Replace in-memory effects and persist cleaned file
    effects.clear()
    effects.update(new_effects)
    save_effects()

    owlry_channel = bot.get_channel(OWLRY_CHANNEL_ID)
    if owlry_channel:
        await owlry_channel.send("🦉 Hedwig is flying again!")

    print(f"[Hedwig] Logged in as {bot.user}")


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN is missing from your .env file!")

# -------------------------
# Background Tasks
# -------------------------
@tasks.loop(minutes=5)
async def cleanup_effects():
    """Remove expired effects from memory and save file."""
    now = datetime.utcnow()
    expired = []

    for uid, data in list(effects.items()):
        new_effects = []
        for e in data.get("effects", []):
            try:
                exp_time = datetime.fromisoformat(e["expires_at"])
            except Exception:
                continue

            if now >= exp_time:
                expired.append((uid, e["uid"]))
            else:
                new_effects.append(e)

        if not new_effects:
            # All effects for this user have expired, so remove them
            del effects[uid]
        else:
            effects[uid]["effects"] = new_effects

    if expired:
        save_effects()

    # --- check for expired alohomora cooldowns ---
    now_ts = time.time()
    to_remove = []
    for user_id, expiry in alohomora_cooldowns.items():
        if now_utc() >= expiry:
            to_remove.append(user_id)

    for user_id in to_remove:
        del alohomora_cooldowns[user_id]
        print(f"[Hedwig] Alohomora cooldown expired for user {user_id}")


# -------------------------
# User Commands
# -------------------------
@bot.command()
async def balance(ctx):
    """Checks your galleon balance."""
    user_id = ctx.author.id
    balance = get_balance(user_id)
    await ctx.send(f"{ctx.author.mention}, you have {balance} galleons.")


@bot.command()
async def points(ctx):
    """Checks the house points."""
    msg = "**House Points**\n"
    sorted_points = sorted(house_points.items(), key=lambda item: item[1], reverse=True)
    for house, points in sorted_points:
        emoji = house_emojis.get(house, "")
        msg += f"{emoji} {house.capitalize()}: {points}\n"
    await ctx.send(msg)


# --- Staff commands ---

@bot.command()
async def award(ctx, member: discord.Member, amount: int, *, reason: str = ""):
    """Awards a member galleons (Staff only)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("You do not have permission to use this command.")

    add_galleons_local(member.id, amount)
    await ctx.send(f"Awarded {amount} galleons to {member.mention}. Reason: {reason}")


@bot.command()
async def deduct(ctx, member: discord.Member, amount: int, *, reason: str = ""):
    """Deducts galleons from a member (Staff only)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("You do not have permission to use this command.")

    remove_galleons_local(member.id, amount)
    await ctx.send(f"Deducted {amount} galleons from {member.mention}. Reason: {reason}")


@bot.command()
async def award_house(ctx, house: str, amount: int, *, reason: str = ""):
    """Awards house points to a house (Staff only)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("You do not have permission to use this command.")

    house = house.lower()
    if house not in house_points:
        return await ctx.send("Invalid house name.")

    house_points[house] += amount
    save_house_points()
    await ctx.send(f"Awarded {amount} points to {house.capitalize()}. Reason: {reason}")


@bot.command()
async def deduct_house(ctx, house: str, amount: int, *, reason: str = ""):
    """Deducts house points from a house (Staff only)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("You do not have permission to use this command.")

    house = house.lower()
    if house not in house_points:
        return await ctx.send("Invalid house name.")

    house_points[house] -= amount
    save_house_points()
    await ctx.send(f"Deducted {amount} points from {house.capitalize()}. Reason: {reason}")


@bot.command()
async def staff_list(ctx):
    """Lists all staff members (Staff only)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("You do not have permission to use this command.")

    staff_roles = [ROLE_IDS["head_of_house"], ROLE_IDS["prefects"]]
    staff_members = []
    for role_id in staff_roles:
        role = ctx.guild.get_role(role_id)
        if role:
            staff_members.extend(role.members)

    msg = "**Staff Members**\n"
    for member in set(staff_members):
        msg += f"- {member.mention} ({member.display_name})\n"
    await ctx.send(msg)


# --- Potions & Effects ---

@bot.command()
async def potion(ctx, name: str):
    """Starts a potion game for a potion."""
    name = name.lower()
    if name not in POTION_LIBRARY:
        return await ctx.send("That's not a recognized potion.")

    if ctx.author.id in active_potions:
        return await ctx.send("You already have an active potion brewing!")

    potion_info = POTION_LIBRARY[name]
    cost = potion_info["cost"]
    if get_balance(ctx.author.id) < cost:
        return await ctx.send(f"You don't have enough galleons to brew {name}! It costs {cost}.")

    add_galleons_local(ctx.author.id, -cost)
    active_potions[ctx.author.id] = {
        "winning": random.randint(1, 5),
        "chosen": False,
        "started_by": ctx.author.id,
        "potion_name": name,
    }
    await ctx.send(
        f"{ctx.author.mention} has started brewing a {name} potion for {cost} galleons. "
        "Choose a number 1-5 with `!choose <number>` to get a random result!"
    )


@bot.command()
async def choose(ctx, number: int):
    """Chooses a number for the active potion game."""
    if ctx.author.id not in active_potions:
        return await ctx.send("You don't have an active potion brewing. Use `!potion <name>` to start one.")

    if active_potions[ctx.author.id]["chosen"]:
        return await ctx.send("You've already made your choice for this potion.")

    if not 1 <= number <= 5:
        return await ctx.send("Please choose a number between 1 and 5.")

    active_potions[ctx.author.id]["chosen"] = True
    winning_number = active_potions[ctx.author.id]["winning"]
    potion_name = active_potions[ctx.author.id]["potion_name"]

    if number == winning_number:
        await ctx.send(f"✨ You chose wisely! The potion works! Applying {potion_name} effect...")
        if potion_name == "alohomora":
            # The alohomora effect is a special role, not a nickname effect
            role = discord.utils.get(ctx.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role:
                await safe_add_role(ctx.author, role)
                alohomora_cooldowns[ctx.author.id] = now_utc() + timedelta(days=1)
                await ctx.send(f"The `Alohomora` spell has been cast! {ctx.author.mention} can now access the Room of Requirement for 24 hours.")
        else:
            await apply_effect(ctx, ctx.author, potion_name)
    else:
        await ctx.send(f"💥 The potion didn't work. The winning number was {winning_number}.")

    del active_potions[ctx.author.id]


@bot.command()
async def cast(ctx, effect_name: str, target: discord.Member):
    """Casts a spell effect on a user."""
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_LIBRARY:
        return await ctx.send("That's not a recognized spell.")

    caster_id = ctx.author.id
    target_id = target.id

    if get_balance(caster_id) < EFFECT_LIBRARY[effect_name]["cost"]:
        return await ctx.send(f"You don't have enough galleons to cast {effect_name}!")

    if effect_name == "alohomora":
        await ctx.send("Alohomora is a potion, not a spell. Use `!potion alohomora` instead.")
        return

    add_galleons_local(caster_id, -EFFECT_LIBRARY[effect_name]["cost"])
    await apply_effect(ctx, target, effect_name)


async def apply_effect(ctx, target: discord.Member, effect_name: str):
    effect_info = EFFECT_LIBRARY[effect_name]
    uid = make_effect_uid()
    expires_at = (datetime.utcnow() + timedelta(minutes=60)).isoformat() # default 1 hr

    if target.id not in active_effects:
        active_effects[target.id] = {
            "original_nick": target.display_name,
            "effects": [],
        }

    active_effects[target.id]["effects"].append({
        "uid": uid,
        "name": effect_name,
        "kind": effect_info["kind"],
        "expires_at": expires_at,
    })
    save_effects()

    kind = effect_info["kind"]

    if kind == "nickname":
        prefix = effect_info.get("prefix_unicode", "")
        suffix = effect_info.get("suffix_unicode", "")
        new_nick = f"{prefix} {active_effects[target.id]['original_nick']} {suffix}"
        await set_nickname(target, new_nick.strip())
        await ctx.send(f"Applied {effect_name} to {target.mention}!")

    elif kind == "truncate":
        length = effect_info["length"]
        original_nick = active_effects[target.id]['original_nick']
        new_nick = original_nick[:len(original_nick) - length]
        await set_nickname(target, new_nick)
        await ctx.send(f"Applied {effect_name} to {target.mention}!")

    elif kind == "role_lumos":
        role = discord.utils.get(ctx.guild.roles, id=ROLE_IDS["lumos"])
        if role:
            await safe_add_role(target, role)
            await set_nickname(target, f"{effect_info['prefix_unicode']} {active_effects[target.id]['original_nick']}")
            await ctx.send(f"Applied {effect_name} to {target.mention}!")

    elif kind == "finite":
        if target.id not in active_effects or not active_effects[target.id]["effects"]:
            await ctx.send(f"There are no active effects to remove from {target.mention}.")
            return

        effects_to_remove = active_effects[target.id]["effects"]
        last_effect = effects_to_remove.pop()

        if last_effect["kind"] == "role_alohomora":
            alohomora_role = discord.utils.get(ctx.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if alohomora_role and alohomora_role in target.roles:
                await safe_remove_role(target, alohomora_role)

        elif last_effect["kind"] == "role_lumos":
            lumos_role = discord.utils.get(ctx.guild.roles, id=ROLE_IDS["lumos"])
            if lumos_role and lumos_role in target.roles:
                await safe_remove_role(target, lumos_role)

        if not effects_to_remove:
            original_nick = active_effects[target.id]["original_nick"]
            await set_nickname(target, original_nick)
            del active_effects[target.id]
        else:
            active_effects[target.id]["effects"] = effects_to_remove
            await set_nickname(target, f"{EFFECT_LIBRARY[effects_to_remove[-1]['name']]['prefix_unicode']} {active_effects[target.id]['original_nick']}")
        
        save_effects()
        await ctx.send(f"Successfully removed the last effect from {target.mention}!")
    
    else:
        await ctx.send("Effect kind not implemented.")


# -------------------------
# BOT STARTUP
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN is missing from your .env file!")

bot.run(TOKEN)