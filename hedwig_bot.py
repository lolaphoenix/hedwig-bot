# hedwig_bot.py
import os
import random
import asyncio
import uuid
import discord
import json
import time
import signal
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta

# -------------------------
# CONFIG / SETUP
# -------------------------
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Channel IDs
OWLRY_CHANNEL_ID = 1410875871249829898
ROOM_OF_REQUIREMENT_ID = 1413134135169646624
GRINGOTTS_CHANNEL_ID = 1413047433016901743

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

# House emojis
house_emojis = {
    "gryffindor": "<:gryffindor:1398846272114524300>",
    "slytherin": "<:slytherin:1398846083463122984>",
    "ravenclaw": "<:ravenclaw:1398846388430835752>",
    "hufflepuff": "<:hufflepuff:1398846494844387379>",
}

# Custom effect emoji mappings
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
    "amortentia": "<:amortentia:1413679525178380369>",
    "polyjuice": "<:polyjuice:1413679815520944158>",
    "finite": "✂️"
}

# Optional unicode versions (for nicknames, etc.)
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
    "amortentia": "💖",
    "polyjuice": "🧪",
    "finite": "✂️"
}

# -------------------------
# PERSISTENCE: data files
# -------------------------
effects = {}  # {user_id: {"effect": str, "expires": timestamp}}
EFFECTS_FILE = "effects.json"
try:
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
except NameError:
    DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)
GALLEONS_FILE = os.path.join(DATA_DIR, "galleons.json")
POINTS_FILE = os.path.join(DATA_DIR, "house_points.json")

# in-memory state (will be loaded on start)
galleons = {}                          # int_user_id -> int
house_points = {h: 0 for h in house_emojis}

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

# -------------------------
# Persistence Functions
# -------------------------

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


# -------------------------
# STATE (OTHER IN-MEMORY)
# -------------------------
last_daily = {}           # user_id -> datetime
active_effects = {}       # user_id -> {"original_nick": str, "effects": [ ... ]}
active_potions = {}       # user_id -> {"winning": int, "chosen": bool, "started_by": id}

alohomora_cooldowns = {}    # target_user_id -> datetime

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

def strip_known_unicode(name: str) -> str:
    """Remove Unicode emoji decorations used by effects/potions from a nickname."""
    if not name:
        return name
    for lib in (EFFECT_LIBRARY, POTION_LIBRARY):
        for v in lib.values():
            for key in ("prefix_unicode", "suffix_unicode"):
                val = v.get(key)
                if val:
                    name = name.replace(val, "")
    return name.strip()

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
        "cost": 50, "kind": "role_alohomora", "duration": 86400,
        "description": "Grants access to the Room of Requirement for 24 hours and starts the potion game."
    },
    "lumos": {
        "cost": 15, "kind": "role_lumos",
        "prefix": "<:lumos:1415595044357931100>", "prefix_unicode": "⭐",
        "suffix_unicode": "⭐",
        "description": "Gives the Lumos role and a star prefix to the nickname."
    },
    "finite": {
        "cost": 10, "kind": "finite", "duration": 0,
        "description": "Finite: removes the most recent spell/potion from a user when cast."
    },
}

POTION_LIBRARY = {
    "felixfelicis": {
        "emoji": "<:felixfelicis:1413679761036673186>",
        "cost": 60, "kind": "potion_luck_good", "prefix": "<:felixfelicis:1414255673973280908>", "prefix_unicode": "🍀",
        "description": "Felix Felicis: improves odds of winning the Alohomora potion game and adds 🍀 to the nickname."
    },
    "draughtlivingdeath": {
        "emoji": "<:draughtoflivingdeath:1413679622041894985>", 
        "cost": 50, "kind": "potion_luck_bad", "prefix": "<:draughtlivingdeath:1414255673973280910>", "prefix_unicode": "💀",
        "description": "Draught of the Living Death: decreases odds of winning Alohomora and adds 💀 to the nickname."
    },
    "amortentia": {
        "emoji": "<:amortentia:1413679525178380369>",
        "cost": 70, "kind": "potion_amortentia", "prefix": "<:amortentia:1414255673973280909>", "prefix_unicode": "💖", "role_id": ROLE_IDS["amortentia"],
        "description": "Amortentia: grants the Amortentia role (color) and adds 💖 to nickname."
    },
    "polyjuice": {
        "emoji": "<:polyjuice:1413679815520944158>",
        "cost": 80, "kind": "potion_polyjuice", "duration": 86400,
        "description": "Polyjuice Potion: randomly grants access to a house common-room role for 24 hours (or backfires)."
    },
    "bezoar": {
        "emoji": "<:bezoar:1415594792217350255>",
        "cost": 30, "kind": "potion_bezoar",
        "description": "Bezoar: removes active potion effects from the target instantly."
    },
}

EFFECT_LIBRARY["polyfail_cat"] = {
    "emoji": "🐱",
    "cost": 0,
    "kind": "nickname",
    "prefix": "🐱",
    "prefix_unicode": "🐱",
    "suffix": "",
    "duration": 86400,
    "description": "Polyjuice misfire! Get whiskers for 24 hours.",
}

# -------------------------
# APPLY / REMOVE EFFECTS
# -------------------------

async def apply_effect_to_member(member: discord.Member, effect_name: str, source: str = "spell", meta: dict = None):
    # safety: ensure the effect exists in either library
    effect_def = EFFECT_LIBRARY.get(effect_name) or POTION_LIBRARY.get(effect_name)
    if not effect_def:
        print(f"[Hedwig] Tried to apply unknown effect: {effect_name}")
        return

    # Only Polyjuice & Alohomora have durations
    duration = effect_def.get("duration", 0)
    expires_at = None
    if duration and duration > 0:
        expires_at = datetime.utcnow() + timedelta(seconds=duration)

    uid = f"{effect_name}_{int(time.time())}"

    emoji_custom = effect_def.get("emoji", "")
    prefix_unicode = effect_def.get("prefix_unicode", "")
    suffix_unicode = effect_def.get("suffix_unicode", "")

    # Store clean nickname base once
    if member.id not in active_effects:
        active_effects[member.id] = {"original_nick": member.display_name, "effects": []}

    entry = {
        "uid": uid,
        "effect": effect_name,
        "name": effect_name,
        "source": source,
        "expires_at": expires_at.isoformat() if expires_at else None,
        **effect_def,
        "prefix_custom": emoji_custom,
        "prefix_unicode": prefix_unicode,
        "suffix_unicode": suffix_unicode,
        "meta": meta or {}
    }

    # Add role immediately if relevant
    role_id = entry.get("role_id")
    if role_id:
        role = member.guild.get_role(role_id)
        if role and role not in member.roles:
            await safe_add_role(member, role)

    # Add to active effects
    active_effects[member.id]["effects"].append(entry)

    # Persist
    effects[str(member.id)] = active_effects[member.id]
    save_effects()

    # schedule expiry and apply visible changes
    if entry.get("kind") in ("potion_polyjuice", "role_alohomora"):
        asyncio.create_task(schedule_expiry(member.id, uid, expires_at))

    await update_member_display(member)


    # Update nickname/roles
    await update_member_display(member)


async def schedule_expiry(user_id: int, uid: str, expires_at: datetime):
    delta = (expires_at - now_utc()).total_seconds()
    if delta > 0:
        await asyncio.sleep(delta)
    member = get_member_from_id(user_id)
    if member:
        await expire_effect(member, uid)


async def expire_effect(member: discord.Member, uid: str):
    if member.id not in active_effects:
        effects.pop(str(member.id), None)
        save_effects()
        return

    expired = next((e for e in active_effects[member.id]["effects"] if e["uid"] == uid), None)
    active_effects[member.id]["effects"] = [
        e for e in active_effects[member.id]["effects"] if e["uid"] != uid
    ]

    if active_effects.get(member.id, {}).get("effects"):
        effects[str(member.id)] = active_effects[member.id]
    else:
        effects.pop(str(member.id), None)
        active_effects.pop(member.id, None)

    save_effects()

    if expired:
        role_id = expired.get("role_id")
        if role_id:
            role = member.guild.get_role(role_id)
            if role and role in member.roles:
                await safe_remove_role(member, role)
    
    # Clean nickname base to remove any leftover Unicode emoji decorations
    clean_nick = strip_known_unicode(active_effects.get(member.id, {}).get("original_nick", member.display_name))
    
    # Update original nickname stored in active_effects
    if member.id in active_effects:
        active_effects[member.id]["original_nick"] = clean_nick

    # Recompute and apply updated nickname
    await update_member_display(member)

async def recompute_nickname(member: discord.Member):
    data = active_effects.get(member.id)
    if not data:
        return

    base = data.get("original_nick", member.display_name)

    # Apply effects in order (stackable)
    for e in data["effects"]:
        kind = e.get("kind")

        if kind == "nickname":
            prefix = e.get("prefix_unicode", "")
            suffix = e.get("suffix_unicode", "")
            base = f"{prefix}{base}{suffix}"

        elif kind == "truncate":
            length = e.get("length", 0)
            if length and len(base) > length:
                base = base[:-length]

        elif kind == "role_lumos":
            prefix = e.get("prefix_unicode", "")
            if prefix:
                base = f"{prefix}{base}"

        elif kind and kind.startswith("potion_"):
            prefix = e.get("prefix_unicode", "")
            if prefix:
                base = f"{prefix}{base}"

    await set_nickname(member, base)


async def update_member_display(member: discord.Member):
    """Refresh nickname and roles from active effects."""
    await recompute_nickname(member)

    user_effects = active_effects.get(member.id, {}).get("effects", [])
    for e in user_effects:
        kind = e.get("kind")

        if kind == "role_lumos":
            role = member.guild.get_role(ROLE_IDS["lumos"])
            if role:
                await safe_add_role(member, role)

        elif kind == "potion_amortentia":
            rid = e.get("role_id")
            role = member.guild.get_role(rid)
            if role:
                await safe_add_role(member, role)

        elif kind == "role_alohomora":
            role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role:
                await safe_add_role(member, role)

        elif kind == "potion_polyjuice":
            chosen = e.get("meta", {}).get("polyhouse")
            if chosen and chosen in ROLE_IDS:
                role = member.guild.get_role(ROLE_IDS[chosen])
                if role:
                    await safe_add_role(member, role)

# -------------------------
# ROOM / ALOHOMORA GAME HELPERS
# -------------------------
def pick_winning_potion():
    return random.randint(1, 5)

async def announce_room_for(member: discord.Member):
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if not room:
        return
    await room.send(f"🔮 Welcome {member.mention}!\nPick a potion with `!choose 1-5`")
    await room.send(" ".join(POTION_EMOJIS))

async def finalize_room_after_choice(member: discord.Member):
    role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
    if role and role in member.roles:
        await safe_remove_role(member, role)
    asyncio.create_task(purge_room_after_delay(1800))

async def purge_room_after_delay(delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if room:
        try:
            await room.purge(limit=100)
        except discord.Forbidden:
            print("Missing permissions to purge room.")
        except Exception as e:
            print("Error purging room:", e)

# -------------------------
# COMMANDS: HELP / MOD
# -------------------------
@bot.command()
async def hedwighelp(ctx):
    msg = (
        "🦉 **Hedwig Help** 🦉\n"
        "✨ Student Commands:\n"
        "`!shopspells` – View available spells\n"
        "`!shoppotions` – View available potions\n"
        "`!cast <spell> @user` – Cast a spell and include a target such as yourself or another person\n"
        "`!drink <potion> @user` – Drink a potion and include a target such as yourself or another person\n"
        "`!balance` – Check your galleons\n"
        "`!daily` – Collect your daily allowance\n"
        "`!points` – View house points\n"
        "`!choose <1–5>` – Choose a potion in Room of Requirement\n"
    )
    await ctx.send(msg)

@bot.command()
async def hedwigmod(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to see mod commands.")
    msg = (
        "⚖️ **Hedwig Moderator Commands** ⚖️\n"
        "`!addpoints <house> <points>` — Add house points\n"
        "`!resetpoints` — Reset house points globally\n"
        "`!givegalleons @user <amount>` — Give galleons to a user (Prefects & Head of House only)\n"
        "`!resetgalleons` — Clear all galleon balances globally\n"
        "`!finite @user`  — Removes most recent spell/potion from a user\n"
        "`!trigger-game [@user]` — Prefects-only test: starts the Alohomora game for a user\n"
    )
    await ctx.send(msg)

# -------------------------
# COMMANDS: HOUSE POINTS
# -------------------------
@bot.command()
async def addpoints(ctx, house: str, points: int):
    house = house.lower()
    if house in house_points:
        house_points[house] += int(points)
        save_house_points()
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
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to reset points.")
    for house in house_points:
        house_points[house] = 0
    save_house_points()
    await ctx.send("🔄 All house points have been reset!")

# -------------------------
# COMMANDS: GALLEON ECONOMY
# -------------------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"💰 {member.display_name} has **{get_balance(member.id)}** galleons.")

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    now = now_utc()
    if user_id in last_daily and now - last_daily[user_id] < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_daily[user_id])
        hrs, rem = divmod(remaining.seconds, 3600)
        mins = rem // 60
        return await ctx.send(f"⏳ You already collected daily. Try again in {hrs}h {mins}m.")
    reward = random.randint(10, 30)
    add_galleons_local(user_id, reward)
    last_daily[user_id] = now
    gringotts = bot.get_channel(GRINGOTTS_CHANNEL_ID)
    if gringotts:
        await gringotts.send(f"💰 {ctx.author.display_name} collected daily allowance and now has {get_balance(user_id)} galleons!")
    else:
        await ctx.send(f"💰 You collected {reward} galleons! You now have {get_balance(user_id)}.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Please provide a positive amount.")
    sender = ctx.author.id
    if get_balance(sender) < amount:
        return await ctx.send("🚫 You don’t have enough galleons.")
    remove_galleons_local(sender, amount)
    add_galleons_local(member.id, amount)
    await ctx.send(f"💸 {ctx.author.display_name} paid {amount} galleons to {member.display_name}!")

@bot.command()
async def givegalleons(ctx, member: discord.Member, amount: int):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("🚫 You don't have permission to give galleons.")
    if amount <= 0:
        return await ctx.send("Please provide a positive amount.")
    add_galleons_local(member.id, amount)
    await ctx.send(f"✨ {member.display_name} received {amount} galleons! They now have {get_balance(member.id)}.")

@bot.command()
async def resetgalleons(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("🚫 You don't have permission to reset galleons.")
    galleons.clear()
    save_galleons()
    await ctx.send("🔄 All galleon balances have been reset.")

@bot.command()
async def leaderboard(ctx):
    if not galleons:
        return await ctx.send("No one has any galleons yet!")
    sorted_balances = sorted(galleons.items(), key=lambda x: x[1], reverse=True)[:10]
    result = "🏦 Gringotts Rich List 🏦\n"
    for i, (user_id, bal) in enumerate(sorted_balances, start=1):
        member = get_member_from_id(int(user_id)) or ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        result += f"{i}. {name} — {bal} galleons\n"
    await ctx.send(result)

# -------------------------
# COMMAND: SHOP (spells + potions)
# -------------------------
@bot.command()
async def shopspells(ctx):
    msg = "🪄 **Spell Shop** 🪄\n\n"
    for name, data in EFFECT_LIBRARY.items():
        if name == "polyfail_cat":
            continue
        # Get emoji from effect_emojis dictionary, fallback to prefix_unicode or empty string
        emoji = effect_emojis.get(name, data.get("prefix_unicode", ""))
        cost = data.get("cost", "?")
        desc = data.get("description", "No description available.")
        msg += f"{emoji} **{name.capitalize()}** — {cost} galleons\n {desc}\n\n"
    msg += "Use `!cast @user` to buy and cast spells!\n"
    await ctx.send(msg)

@bot.command()
async def shoppotions(ctx):
    msg = "🍷 **Potion Shop** 🍷\n\n"
    for name, data in POTION_LIBRARY.items():
        if name == "polyfail_cat":
            continue
        emoji = data.get("emoji") or data.get("prefix_unicode") or ""
        cost = data.get("cost", "?")
        desc = data.get("description", "No description available.")
        msg += f"{emoji} **{name.capitalize()}** — {cost} galleons\n   {desc}\n\n"
    msg += "Use `!drink <potion> [@user]` to buy and drink potions.\n"
    await ctx.send(msg)


# -------------------------
# COMMAND: CAST (spells)
# -------------------------
@bot.command()
async def cast(ctx, spell: str, member: discord.Member):
    caster = ctx.author
    spell = spell.lower()

    if spell not in EFFECT_LIBRARY:
        return await ctx.send("❌ That spell doesn’t exist. Check the shop with `!shopspells`.")

    ed = EFFECT_LIBRARY[spell]
    cost = ed.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("💸 You don’t have enough galleons to cast that spell!")

    # Alohomora has cooldown
    if spell == "alohomora":
        now = now_utc()
        last = alohomora_cooldowns.get(member.id)
        if last and now - last < timedelta(hours=24):
            return await ctx.send("⏳ Alohomora can only be cast on this user once every 24 hours.")
        alohomora_cooldowns[member.id] = now

    # Finite: remove most recent effect
    if spell == "finite":
        remove_galleons_local(caster.id, cost)
        if member.id not in active_effects or not active_effects[member.id]["effects"]:
            return await ctx.send("❌ That user has no active spells/potions to finite.")

        effects_list = active_effects[member.id]["effects"]
        entry = effects_list[-1]  # remove the most recent
        await expire_effect(member, entry["uid"])
        return await ctx.send(f"✨ {caster.display_name} cast Finite on {member.display_name} — removed **{entry['effect']}**.")

    # Alohomora starts the potion game
    if spell == "alohomora":
        active_potions[member.id] = {"winning": pick_winning_potion(), "chosen": False, "started_by": caster.id}
        await announce_room_for(member)
        return

    # Default: any other spell
    remove_galleons_local(caster.id, cost)
    await apply_effect_to_member(member, spell, source="spell")
    await ctx.send(f"✨ {caster.display_name} cast **{spell.capitalize()}** on {member.display_name}!")



# -------------------------
# COMMAND: DRINK (potions)
# -------------------------
@bot.command()
async def drink(ctx, potion: str, member: discord.Member = None):
    potion = potion.lower()
    member = member or ctx.author
    caster = ctx.author

    if potion not in POTION_LIBRARY:
        return await ctx.send("❌ That potion doesn’t exist. Check the shop with `!shoppotions`.")

    pd = POTION_LIBRARY[potion]
    cost = pd.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("💸 You don’t have enough galleons to buy that potion!")

    # Polyjuice: prevent stacking
    if pd.get("kind") == "potion_polyjuice":
        if member.id in active_effects and any(e.get("effect") == "polyjuice" for e in active_effects[member.id]["effects"]):
            return await ctx.send("You try to imbibe another Polyjuice, but can't get it down. 🤢 No galleons have been spent. Try again later.")

    remove_galleons_local(caster.id, cost)

    # Bezoar (cleanse potions only)
    if pd["kind"] == "potion_bezoar":
        if member.id in active_effects:
            to_remove = [e["uid"] for e in active_effects[member.id]["effects"]
                         if (e.get("kind") or "").startswith("potion_") or e.get("effect") in POTION_LIBRARY]
            for uid in to_remove:
                await expire_effect(member, uid)
        await ctx.send(f"🧪 {caster.display_name} used Bezoar on {member.display_name}. Potion effects removed.")
        return

    # Polyjuice special-handling (24h only)
    if pd["kind"] == "potion_polyjuice":
        houses = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]
        chosen = random.choice(houses)
        user_house = get_user_house(member)
        if user_house == chosen:
            # backfired
            await apply_effect_to_member(member, "polyfail_cat", source="potion")
            await ctx.send(f"🧪 {caster.display_name} gave Polyjuice to {member.display_name}... it misfired! You get whiskers 🐱 for 24 hours.")
        else:
            meta = {"polyhouse": chosen}
            await apply_effect_to_member(member, "polyjuice", source="potion", meta=meta)
            display_house = chosen.capitalize()
            await ctx.send(f"🧪 {caster.display_name} gave Polyjuice to {member.display_name} — you can access the **{display_house}** common room for 24 hours!")
        return

    # All other potions: permanent until finite/cleareffects
    await apply_effect_to_member(member, potion, source="potion", meta={"permanent": True})
    await ctx.send(f"🧪 {caster.display_name} gave **{potion.capitalize()}** to {member.display_name}!")

# -------------------------
# COMMAND: CHOOSE (Room of Requirement)
# -------------------------
@bot.command()
async def choose(ctx, number: int):
    if ctx.channel.id != ROOM_OF_REQUIREMENT_ID:
        return await ctx.send(f"🚪 Please use this command in <#{ROOM_OF_REQUIREMENT_ID}>.")
    if number < 1 or number > 5:
        return await ctx.send("🚫 Pick a number between 1 and 5.")
    user_id = ctx.author.id
    if user_id not in active_potions:
        return await ctx.send("❌ You don’t have an active potion challenge. Cast Alohomora or drink a potion first.")
    if active_potions[user_id]["chosen"]:
        return await ctx.send("🧪 You already chose a potion for this challenge.")
    active_potions[user_id]["chosen"] = True
    winning = active_potions[user_id]["winning"]
    # luck modifiers
    luck = 0.0
    data = active_effects.get(user_id)
    if data:
        for e in data["effects"]:
            if e.get("effect") == "felixfelicis":
                luck += 0.5
            if e.get("effect") == "draughtlivingdeath":
                luck -= 0.5
    forced_win = (luck > 0 and random.random() < luck)
    forced_miss = (luck < 0 and random.random() < abs(luck))
    final_choice = number
    if forced_win:
        final_choice = winning
    elif forced_miss:
        opts = [i for i in range(1, 6) if i != winning]
        final_choice = random.choice(opts)
    if final_choice == winning:
        add_galleons_local(user_id, 100)
        await ctx.send(f"🎉 {ctx.author.mention} picked potion {number} and won **100 galleons**!")
    else:
        await ctx.send(f"💨 {ctx.author.mention} picked potion {number}... nothing happened. Better luck next time!")
    await finalize_room_after_choice(ctx.author)
    del active_potions[user_id]

# -------------------------
# COMMAND: TRIGGER-GAME (testing) - restricted to Prefects/Head
# -------------------------
@bot.command(name="trigger-game", aliases=["trigger_game", "triggergame"])
async def trigger_game(ctx, member: discord.Member = None):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to trigger the test game.")
    member = member or ctx.author

    # Give Alohomora (free test) and start the game
    await apply_effect_to_member(member, "alohomora", source="test")
    winning = pick_winning_potion()
    active_potions[member.id] = {"winning": winning, "chosen": False, "started_by": ctx.author.id}
    await announce_room_for(member)

    # Reveal the correct answer to the staff who ran the test (DM preferred)
    try:
        await ctx.author.send(f"[TEST] The winning potion for {member.display_name} is **{winning}** (use this to validate the game).")
    except Exception:
        await ctx.send(f"[TEST MODE] The winning potion for {member.mention} is **{winning}**. (Visible because DM failed)")

    await ctx.send(f"🧪 Testing potion game started for {member.mention} (Prefects test).")

# -------------------------
# COMMAND: FINITE (manual/mod + purchasable via !cast finite)
# -------------------------
@bot.command()
async def finite(ctx, member: discord.Member, effect_name: str = None):
    if member.id not in active_effects:
        return await ctx.send("No active spells/potions on this user.")

    effects_list = active_effects[member.id]["effects"]

    if effect_name:
        effect_name = effect_name.lower().strip()
        # Search by "effect" field (safer than "name")
        idx = None
        for i in range(len(effects_list)-1, -1, -1):
            if effects_list[i].get("effect", "").lower() == effect_name:
                idx = i
                break

        if idx is None:
            return await ctx.send(f"That effect (`{effect_name}`) was not found on {member.display_name}.")

        entry = effects_list[idx]
        await expire_effect(member, entry["uid"])
        return await ctx.send(f"✨ Removed **{entry['effect']}** from {member.display_name}.")
    else:
        # Default: remove the most recent effect
        last = effects_list[-1]
        await expire_effect(member, last["uid"])
        return await ctx.send(f"✨ Removed the most recent effect (**{last['effect']}**) from {member.display_name}.")

# -------------------------
# CLEAR EFFECTS COMMAND
# -------------------------

@bot.command()
async def cleareffects(ctx, member: discord.Member = None):
    """Admin: clear all active effects for a user (or everyone if none)."""
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to use this.")

    if member:
        active_effects.pop(member.id, None)
        effects.pop(str(member.id), None)
        save_effects()
        await update_member_display(member)
        await ctx.send(f"🧹 Cleared all active effects for {member.display_name}.")
    else:
        active_effects.clear()
        effects.clear()
        save_effects()
        await ctx.send("🧹 Cleared ALL active effects for everyone.")


# -------------------------
# STARTUP / RUN
# -------------------------
@bot.event
async def on_ready():
    if not cleanup_effects.is_running():
        cleanup_effects.start()
    load_galleons()
    load_house_points()
    load_effects()

    guild = bot.get_guild(1398801863549259796)

    new_effects = {}  # <- only keep active effects

    # Rehydrate saved effects
    for uid, data in effects.items():
        member = guild.get_member(int(uid)) if guild else None
        if not member:
            continue

        # Clean nickname so we don't stack emojis forever
        clean_nick = strip_known_unicode(data.get("original_nick", member.display_name))

        active_effects[member.id] = {
            "original_nick": clean_nick,
            "effects": []
        }

        for e in data.get("effects", []):
            try:
                exp_time = datetime.fromisoformat(e["expires_at"])
                # Only reapply if still valid
                if exp_time > datetime.utcnow():
                    active_effects[member.id]["effects"].append(e)

                    # Schedule expiry only for temporary ones
                    if e.get("kind") in ("potion_polyjuice", "role_alohomora"):
                        asyncio.create_task(schedule_expiry(member.id, e["uid"], exp_time))
                else:
                    print(f"[Hedwig] Removing expired effect for {member.display_name}")
            except Exception as err:
                print(f"[Hedwig] Error restoring effect for {member.display_name}: {err}")

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

        data["effects"] = new_effects
        if not new_effects:
            effects.pop(uid, None)

    if expired:
        save_effects()
        print(f"[Hedwig] Cleaned up {len(expired)} expired effects")



bot.run(TOKEN)