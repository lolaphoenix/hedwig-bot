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
    "finite": "âœ‚ï¸"
}

# Optional unicode versions (for nicknames, etc.)
effect_unicode = {
    "tarantallegra": "ðŸ’ƒ",
    "serpensortia": "ðŸ",
    "lumos": "âœ¨",
    "incendio": "ðŸ”¥",
    "herbifors": "ðŸŒ¿",
    "ebublio": "ðŸ«§",
    "diffindo": "âœ‚ï¸",
    "confundo": "ðŸŒ€",
    "alohomora": "ðŸ—ï¸",
    "aguamenti": "ðŸ’§",
    "amortentia": "ðŸ’–",
    "bezoar": "ðŸ’Š",
    "felixfelicis": "ðŸ€",
    "draughtlivingdeath": "ðŸ’€",
    "amortentia": "ðŸ’–",
    "polyjuice": "ðŸ§ª",
    "finite": "âœ‚ï¸"
}

# New global dictionaries for dueling state
active_duels = {}
duel_cooldowns = {}

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
DUEL_COOLDOWNS_FILE = os.path.join(DATA_DIR, "duel_cooldowns.json")

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
            # JSON keys are strings â€” convert to ints
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

# --- duel persistence ---

def load_duel_cooldowns():
    global duel_cooldowns
    try:
        if os.path.exists(DUEL_COOLDOWNS_FILE):
            with open(DUEL_COOLDOWNS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            duel_cooldowns = {int(k): datetime.fromisoformat(v) for k, v in raw.items()}
            print(f"[Hedwig] loaded {len(duel_cooldowns)} duel cooldowns from {DUEL_COOLDOWNS_FILE}")
        else:
            duel_cooldowns = {}
            save_duel_cooldowns()
            print(f"[Hedwig] created new duel cooldowns file at {DUEL_COOLDOWNS_FILE}")
    except Exception as e:
        print("[Hedwig] Failed to load duel cooldowns:", e)
        duel_cooldowns = {}

def save_duel_cooldowns():
    try:
        tmp = DUEL_COOLDOWNS_FILE + ".tmp"
        serializable = {str(k): v.isoformat() for k, v in duel_cooldowns.items()}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
        os.replace(tmp, DUEL_COOLDOWNS_FILE)
    except Exception as e:
        print("[Hedwig] Failed to save duel cooldowns:", e)

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
# PERSISTENCE: Dueling
# -------------------------

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
        "prefix": "<:aguamenti:1415595031644999742>", "prefix_unicode": "ðŸŒŠ",
        "suffix": "<:aguamenti:1415595031644999742>", "suffix_unicode": "ðŸŒŠ",
        "description": "Surrounds the target's nickname with water."
    },
    "confundo": {
        "cost": 25, "kind": "nickname",
        "prefix": "<:confundo:1415595034769625199>", "prefix_unicode": "â“CONFUNDED - ",
        "suffix": "", "suffix_unicode": "â“",
        "description": "Prefixes CONFUNDED to the target's nickname."
    },
    "diffindo": {
        "cost": 30, "kind": "truncate",
        "length": 5,
        "description": "Removes the last 5 characters of the target's nickname."
    },
    "ebublio": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:ebublio:1415595038397693982>", "prefix_unicode": "ðŸ«§",
        "suffix": "<:ebublio:1415595038397693982>", "suffix_unicode": "ðŸ«§",
        "description": "Surrounds the target's nickname with bubbles."
    },
    "herbifors": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:herbifors:1415595039882481674>", "prefix_unicode": "ðŸŒ¸",
        "suffix": "<:herbifors:1415595039882481674>", "suffix_unicode": "ðŸŒ¸",
        "description": "Gives the target a floral nickname."
    },
    "serpensortia": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:serpensortia:1415595048124289075>", "prefix_unicode": "ðŸ",
        "suffix": "<:serpensortia:1415595048124289075>", "suffix_unicode": "ðŸ",
        "description": "Surrounds the target's nickname with snake emojis."
    },
    "tarantallegra": {
        "cost": 20, "kind": "nickname",
        "prefix": "<:tarantallegra:1415595049411936296>", "prefix_unicode": "ðŸ’ƒ",
        "suffix": "<:tarantallegra:1415595049411936296>", "suffix_unicode": "ðŸ’ƒ",
        "description": "Adds dancing emojis around the target's nickname."
    },
    "incendio": {
        "cost": 25, "kind": "nickname",
        "prefix": "<:incendio:1415595041191235718>", "prefix_unicode": "ðŸ”¥",
        "suffix": "<:incendio:1415595041191235718>", "suffix_unicode": "ðŸ”¥",
        "description": "Adds flames to the target's nickname."
    },
    "alohomora": {
        "cost": 50, "kind": "role_alohomora", "duration": 86400,
        "description": "Grants access to the Room of Requirement for 24 hours and starts the potion game."
    },
    "lumos": {
        "cost": 15, "kind": "role_lumos",
        "prefix": "<:lumos:1415595044357931100>", "prefix_unicode": "â­",
        "suffix_unicode": "â­",
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
        "cost": 60, "kind": "potion_luck_good", "prefix": "<:felixfelicis:1414255673973280908>", "prefix_unicode": "ðŸ€",
        "description": "Felix Felicis: improves odds of winning the Alohomora potion game and adds ðŸ€ to the nickname."
    },
    "draughtlivingdeath": {
        "emoji": "<:draughtoflivingdeath:1413679622041894985>", 
        "cost": 50, "kind": "potion_luck_bad", "prefix": "<:draughtlivingdeath:1414255673973280910>", "prefix_unicode": "ðŸ’€",
        "description": "Draught of the Living Death: decreases odds of winning Alohomora and adds ðŸ’€ to the nickname."
    },
    "amortentia": {
        "emoji": "<:amortentia:1413679525178380369>",
        "cost": 70, "kind": "potion_amortentia", "prefix": "<:amortentia:1414255673973280909>", "prefix_unicode": "ðŸ’–", "role_id": ROLE_IDS["amortentia"],
        "description": "Amortentia: grants the Amortentia role (color) and adds ðŸ’– to nickname."
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
    "emoji": "ðŸ±",
    "cost": 0,
    "kind": "nickname",
    "prefix": "ðŸ±",
    "prefix_unicode": "ðŸ±",
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
    
    # The next function call is what will now handle the nickname refresh.
    await update_member_display(member)

async def recompute_nickname(member: discord.Member):
    data = active_effects.get(member.id)
    if not data:
        # If no active effects, reset to original display name.
        if member.display_name != member.name:
             await set_nickname(member, None)
        return

    # Start with the member's current display name, which is the most reliable base.
    base_name = data.get("original_nick", member.display_name)
    
    # We need to find the *true* base name, without any effects applied yet.
    # The safest way is to clear all and re-apply.
    await set_nickname(member, base_name)
    
    # Now that the nickname is reset, get the display name and build from there.
    display_name = member.display_name
    
    # Apply effects in order (stackable)
    for e in data["effects"]:
        kind = e.get("kind")

        if kind == "nickname":
            prefix = e.get("prefix_unicode", "")
            suffix = e.get("suffix_unicode", "")
            display_name = f"{prefix}{display_name}{suffix}"

        elif kind == "truncate":
            length = e.get("length", 0)
            if length and len(display_name) > length:
                display_name = display_name[:-length]

        elif kind == "role_lumos":
            prefix = e.get("prefix_unicode", "")
            if prefix:
                display_name = f"{prefix}{display_name}"

        elif kind and kind.startswith("potion_"):
            prefix = e.get("prefix_unicode", "")
            if prefix:
                display_name = f"{prefix}{display_name}"
    
    await set_nickname(member, display_name)


async def update_member_display(member: discord.Member):
    """Refresh nickname and roles from active effects."""
    user_effects = active_effects.get(member.id, {}).get("effects", [])

    # First, handle roles, as they are independent of the nickname.
    # Add all necessary roles for the active effects.
    for e in user_effects:
        kind = e.get("kind")
        if kind == "role_lumos":
            role = member.guild.get_role(ROLE_IDS["lumos"])
            if role and role not in member.roles:
                await safe_add_role(member, role)
        elif kind == "potion_amortentia":
            rid = e.get("role_id")
            role = member.guild.get_role(rid)
            if role and role not in member.roles:
                await safe_add_role(member, role)
        elif kind == "role_alohomora":
            role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
            if role and role not in member.roles:
                await safe_add_role(member, role)
        elif kind == "potion_polyjuice":
            chosen = e.get("meta", {}).get("polyhouse")
            if chosen and chosen in ROLE_IDS:
                role = member.guild.get_role(ROLE_IDS[chosen])
                if role and role not in member.roles:
                    await safe_add_role(member, role)

    # Now, recompute and set the nickname based on the roles that were added.
    await recompute_nickname(member)

# -------------------------
# DUEL SEQUENCE
# -------------------------

async def start_duel_sequence(ctx, challenger, challenged):
    outcomes = [
        "casts Expelliarmus on",
        "casts Stupefy on",
        "casts Impedimenta on",
        "casts Petrificus Totalus on",
        "casts Confundo on"
    ]

    await ctx.send(f"ðŸ’¥ WELCOME TO THE DUEL! ðŸ’¥\n**{challenger.mention}** vs **{challenged.mention}**")
    await asyncio.sleep(10)
    await ctx.send("Wands at the ready!")
    await asyncio.sleep(5)
    await ctx.send(f"*{challenger.display_name} and {challenged.display_name} lift their wands, turn their backs, and begin walking to the end...*")
    await asyncio.sleep(3)
    await ctx.send("On the count of three, type `!duel cast` to cast your spell!")
    await asyncio.sleep(5)
    await ctx.send("Three...")
    await asyncio.sleep(2)
    await ctx.send("Two...")
    await asyncio.sleep(1)
    await ctx.send("One... **GO**!")

    winner = None
    loser = None
    
    try:
        def check(m):
            return m.content.lower() == '!duel cast' and m.author in [challenger, challenged] and m.channel == ctx.channel

        msg = await bot.wait_for('message', check=check, timeout=10.0)
        winner = msg.author
        loser = challenger if winner == challenged else challenged

        random_spell = random.choice(outcomes)
        await ctx.send(f"*{winner.display_name} {random_spell} {loser.display_name} and successfully disarms them!*")
        add_galleons_local(winner.id, 100)
        await ctx.send(f"ðŸŽ‰ Congratulations **{winner.mention}**! You've won **100 Galleons**!")
        
    except asyncio.TimeoutError:
        await ctx.send("âŒ No one cast their spell in time! The duel is a draw. No galleons were won.")
        winner = challenger
        loser = challenged

    finally:
        # This block always runs, whether there was a winner or a timeout
        now = dt.datetime.utcnow()
        duel_cooldowns[winner.id] = now
        duel_cooldowns[loser.id] = now
        save_duel_cooldowns()

# -------------------------
# ROOM / ALOHOMORA GAME HELPERS
# -------------------------
def pick_winning_potion():
    return random.randint(1, 5)

async def announce_room_for(member: discord.Member):
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if not room:
        return
    await room.send(f"ðŸ”® Welcome {member.mention}!\nPick a potion with `!choose 1-5`")
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
        "ðŸ¦‰ **Hedwig Help** ðŸ¦‰\n"
        "âœ¨ Student Commands:\n"
        "`!shopspells` â€“ View available spells in Dueling Club\n"
        "`!shoppotions` â€“ View available potions in Dueling Club \n"
        "`!cast <spell> @user` â€“ Cast a spell and include a target such as yourself or another person in Dueling Club\n"
        "`!drink <potion> @user` â€“ Drink a potion and include a target such as yourself or another person in Dueling Club\n"
        "`!balance` â€“ Check your galleons\n"
        "`!daily` â€“ Collect your daily allowance\n"
        "`!points` â€“ View house points\n"
        "`!choose <1â€“5>` â€“ Choose a potion in Room of Requirement to play the game.\n"
    )
    await ctx.send(msg)

@bot.command()
async def hedwigmod(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("âŒ You donâ€™t have permission to see mod commands.")
    msg = (
        "âš–ï¸ **Hedwig Moderator Commands** âš–ï¸\n"
        "`!addpoints <house> <points>` â€” Add house points\n"
        "`!resetpoints` â€” Reset house points globally\n"
        "`!givegalleons @user <amount>` â€” Give galleons to a user (Prefects & Head of House only)\n"
        "`!resetgalleons` â€” Clear all galleon balances globally\n"
        "`!clear [number]` â€” Clears a number of messages (default 100) from the Dueling Club or Room of Requirement channels.\n"
        "`!cast finite @user`Â  â€” Removes most recent spell/potion from a user\n"
        "`!trigger-game [@user]` â€” Prefects-only test: starts the Alohomora game for a user\n"
    )
    await ctx.send(msg)

# -------------------------
# COMMANDS: DUEL
# -------------------------

@bot.command()
async def duel(ctx, challenged_user: discord.Member = None):
    # Restrict to dueling club
    if ctx.channel.id != DUELING_CLUB_ID:
        return await ctx.send("âŒ Duels can only be initiated in the Dueling Club.")

    challenger = ctx.author

    # Check for arguments
    if not challenged_user:
        return await ctx.send("âŒ You must challenge someone to a duel! Use `!duel @username`.")

    if challenged_user.bot:
        return await ctx.send("âŒ You cannot challenge a bot to a duel.")

    if challenger == challenged_user:
        return await ctx.send("âŒ You cannot duel yourself.")

    # Check for cooldowns
    now = dt.datetime.utcnow()
    if challenger.id in duel_cooldowns and (now - duel_cooldowns[challenger.id]).total_seconds() < 86400: # 86400 seconds = 24 hours
        return await ctx.send("â³ You have already dueled today. Wait 24 hours to duel again.")
    if challenged_user.id in duel_cooldowns and (now - duel_cooldowns[challenged_user.id]).total_seconds() < 86400:
        return await ctx.send(f"â³ {challenged_user.display_name} has already dueled today.")
        
    # Check if a duel is already in progress for either user
    if challenger.id in active_duels or challenged_user.id in active_duels:
        return await ctx.send("âŒ One of you is already in a duel.")

    # Store the duel request
    active_duels[challenger.id] = {
        'challenged': challenged_user,
        'channel': ctx.channel
    }
    
    # Send challenge message and wait for confirmation
    await ctx.send(f"âš”ï¸ **{challenged_user.mention}**, you have been challenged to a wizard's duel by **{challenger.mention}**! Do you accept? Type `!duelconfirm` to confirm.")

@bot.command(name='duelconfirm')
async def duel_confirm(ctx):
    challenger = None
    challenged = ctx.author
    
    # Find the duel challenge
    for k, v in active_duels.items():
        if v['challenged'].id == challenged.id:
            challenger = ctx.guild.get_member(k)
            break
            
    if not challenger:
        return await ctx.send("âŒ You have not been challenged to a duel.")

    # Start the duel sequence
    active_duels.pop(challenger.id, None) # Use .pop() for safer deletion
    await start_duel_sequence(ctx, challenger, challenged)

@bot.command(name='duelcast')
async def duel_cast(ctx):
    # This command is handled by the wait_for, so it just returns if called directly
    return

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
    result = "ðŸ† Current House Points ðŸ†\n"
    for house, pts in house_points.items():
        result += f"{house_emojis[house]} {house.capitalize()}: {pts}\n"
    await ctx.send(result)

@bot.command()
async def resetpoints(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("âŒ You donâ€™t have permission to reset points.")
    for house in house_points:
        house_points[house] = 0
    save_house_points()
    await ctx.send("ðŸ”„ All house points have been reset!")

# -------------------------
# COMMANDS: GALLEON ECONOMY
# -------------------------
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"ðŸ’° {member.display_name} has **{get_balance(member.id)}** galleons.")

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    now = now_utc()
    if user_id in last_daily and now - last_daily[user_id] < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last_daily[user_id])
        hrs, rem = divmod(remaining.seconds, 3600)
        mins = rem // 60
        return await ctx.send(f"â³ You already collected daily. Try again in {hrs}h {mins}m. You can use !remindme and I'll ping you when it's ready.")
    reward = random.randint(10, 30)
    add_galleons_local(user_id, reward)
    last_daily[user_id] = now
    gringotts = bot.get_channel(GRINGOTTS_CHANNEL_ID)
    if gringotts:
        await gringotts.send(f"ðŸ’° {ctx.author.display_name} collected daily allowance and now has {get_balance(user_id)} galleons!")
    else:
        await ctx.send(f"ðŸ’° You collected {reward} galleons! You now have {get_balance(user_id)}.")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Please provide a positive amount.")
    sender = ctx.author.id
    if get_balance(sender) < amount:
        return await ctx.send("ðŸš« You donâ€™t have enough galleons.")
    remove_galleons_local(sender, amount)
    add_galleons_local(member.id, amount)
    await ctx.send(f"ðŸ’¸ {ctx.author.display_name} paid {amount} galleons to {member.display_name}!")

@bot.command()
async def givegalleons(ctx, member: discord.Member, amount: int):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("ðŸš« You don't have permission to give galleons.")
    if amount <= 0:
        return await ctx.send("Please provide a positive amount.")
    add_galleons_local(member.id, amount)
    await ctx.send(f"âœ¨ {member.display_name} received {amount} galleons! They now have {get_balance(member.id)}.")

@bot.command()
async def resetgalleons(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("ðŸš« You don't have permission to reset galleons.")
    galleons.clear()
    save_galleons()
    await ctx.send("ðŸ”„ All galleon balances have been reset.")

@bot.command()
async def leaderboard(ctx):
    if not galleons:
        return await ctx.send("No one has any galleons yet!")
    sorted_balances = sorted(galleons.items(), key=lambda x: x[1], reverse=True)[:10]
    result = "ðŸ¦ Gringotts Rich List ðŸ¦\n"
    for i, (user_id, bal) in enumerate(sorted_balances, start=1):
        member = get_member_from_id(int(user_id)) or ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        result += f"{i}. {name} â€” {bal} galleons\n"
    await ctx.send(result)

@bot.command()
async def remindme(ctx):
    """Set a reminder when your !daily is ready again."""
    user_id = ctx.author.id
    now = now_utc()

    # If they've never used daily
    if user_id not in last_daily:
        return await ctx.send("âŒ You havenâ€™t collected your daily yet. Use `!daily` first!")

    # Time remaining until reset
    elapsed = now - last_daily[user_id]
    if elapsed >= timedelta(hours=24):
        return await ctx.send("âœ… Your daily is already ready! Use `!daily` now.")

    remaining = timedelta(hours=24) - elapsed
    hrs, rem = divmod(remaining.seconds, 3600)
    mins = rem // 60

    await ctx.send(f"â³ Okay {ctx.author.display_name}, Iâ€™ll remind you in {hrs}h {mins}m when your daily is ready again.")

    async def send_reminder():
        await asyncio.sleep(remaining.total_seconds())
        gringotts = bot.get_channel(GRINGOTTS_CHANNEL_ID)
        if gringotts:
            await gringotts.send(f"ðŸ’° {ctx.author.mention}, your daily galleons are ready to collect!")

    asyncio.create_task(send_reminder())

# -------------------------
# COMMAND: SHOP (spells + potions)
# -------------------------
@bot.command()
async def shopspells(ctx):
    if ctx.channel.id not in [OWLRY_CHANNEL_ID, DUELING_CLUB_ID]:
        return await ctx.send("âŒ This command can only be used in the Dueling Club.")
   
    msg = "ðŸª„ **Spell Shop** ðŸª„\n\n"
    for name, data in EFFECT_LIBRARY.items():
        if name == "polyfail_cat":
            continue
        # Get emoji from effect_emojis dictionary, fallback to prefix_unicode or empty string
        emoji = effect_emojis.get(name, data.get("prefix_unicode", ""))
        cost = data.get("cost", "?")
        desc = data.get("description", "No description available.")
        msg += f"{emoji} **{name.capitalize()}** â€” {cost} galleons\n {desc}\n\n"
    msg += "Use `!cast @user` to buy and cast spells!\n"
    await ctx.send(msg)

@bot.command()
async def shoppotions(ctx):
    if ctx.channel.id not in [OWLRY_CHANNEL_ID, DUELING_CLUB_ID]:
        return await ctx.send("âŒ This command can only be used in the Dueling Club.")
    msg = "ðŸ· **Potion Shop** ðŸ·\n\n"
    for name, data in POTION_LIBRARY.items():
        if name == "polyfail_cat":
            continue
        emoji = data.get("emoji") or data.get("prefix_unicode") or ""
        cost = data.get("cost", "?")
        desc = data.get("description", "No description available.")
        msg += f"{emoji} **{name.capitalize()}** â€” {cost} galleons\n   {desc}\n\n"
    msg += "Use `!drink <potion> [@user]` to buy and drink potions.\n"
    await ctx.send(msg)


# -------------------------
# COMMAND: CAST (spells)
# -------------------------
@bot.command()
async def cast(ctx, spell: str, member: discord.Member):
    # channel restriction: supports OWLRY + optional DUELING_CLUB_ID if defined
    allowed = {OWLRY_CHANNEL_ID}
    if "DUELING_CLUB_ID" in globals():
        allowed.add(DUELING_CLUB_ID)
    if ctx.channel.id not in allowed:
        return await ctx.send("âŒ This command can only be used in the Dueling Club or the Owlry channel.")

    caster = ctx.author
    spell = spell.lower()

    # basic validation
    if spell not in EFFECT_LIBRARY:
        return await ctx.send("âŒ That spell doesnâ€™t exist. Check the shop with `!shopspells`.")

    ed = EFFECT_LIBRARY[spell]
    cost = ed.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("ðŸ’¸ You donâ€™t have enough galleons to cast that spell!")

    # ---- Alohomora special (exclusive role + game) ----
    if spell == "alohomora":
        now = now_utc()
        last = alohomora_cooldowns.get(member.id)
        if last and now - last < timedelta(hours=24):
            return await ctx.send("â³ Alohomora can only be cast on this user once every 24 hours.")
        alohomora_cooldowns[member.id] = now

        # Ensure exclusivity: remove the Alohomora role from anyone who already has it
        role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
        if role:
            for m in member.guild.members:
                if role in m.roles:
                    await safe_remove_role(m, role)

        # charge + apply + give role + start game
        remove_galleons_local(caster.id, cost)
        await apply_effect_to_member(member, spell, source="spell")

        active_potions[member.id] = {"winning": pick_winning_potion(), "chosen": False, "started_by": caster.id}
        if role:
            await safe_add_role(member, role)
        await announce_room_for(member)

        await ctx.send(f"âœ¨ {caster.display_name} cast **Alohomora** on {member.display_name}! The Room of Requirement is open.")
        return

    # ---- Diffindo special: fails if nickname <= 5 chars, no charge ----
    if spell == "diffindo":
        if len(member.display_name) <= 5:
            return await ctx.send("Your spell bounces off the wall and misses its target. No galleons have been spent. Try another target.")

    # ---- Finite: remove the most recent effect (or named) ----
    if spell == "finite":
        # verify there is something to remove
        if member.id not in active_effects or not active_effects[member.id]["effects"]:
            return await ctx.send("âŒ That user has no active spells/potions to finite.")

        effects_list = active_effects[member.id]["effects"]
        last_entry = effects_list[-1]
        last_effect_name = last_entry.get("effect")

        # Prevent using Finite on Alohomora (policy in your code) â€” don't charge
        if last_effect_name == "alohomora":
            return await ctx.send(f"ðŸª„ The spell bounces back! You cannot use Finite on Alohomora. No galleons were spent.")

        # Disallow Finite on potions (your rule) â€” don't charge
        if last_effect_name in POTION_LIBRARY:
            return await ctx.send("âœ‚ï¸ Finite can only be used on spells, not potions.")

        # Charge and remove the last effect
        remove_galleons_local(caster.id, cost)
        await expire_effect(member, last_entry["uid"])
        return await ctx.send(f"âœ¨ {caster.display_name} cast Finite on {member.display_name} â€” removed **{last_effect_name}**.")

    # ---- All other spells (standard flow) ----
    remove_galleons_local(caster.id, cost)
    await apply_effect_to_member(member, spell, source="spell")
    await ctx.send(f"âœ¨ {caster.display_name} cast **{spell.capitalize()}** on {member.display_name}!")

# -------------------------
# COMMAND: DRINK (potions)
# -------------------------
@bot.command()
async def drink(ctx, potion: str, member: discord.Member = None):
    if ctx.channel.id not in [OWLRY_CHANNEL_ID, DUELING_CLUB_ID]:
        return await ctx.send("âŒ This command can only be used in the Dueling Club.")

    potion = potion.lower()
    member = member or ctx.author
    caster = ctx.author

    if potion not in POTION_LIBRARY:
        return await ctx.send("âŒ That potion doesnâ€™t exist. Check the shop with `!shoppotions`.")

    pd = POTION_LIBRARY[potion]
    cost = pd.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("ðŸ’¸ You donâ€™t have enough galleons to buy that potion!")

    # Check for the 24-hour cooldown on Polyjuice
    if pd.get("kind") == "potion_polyjuice":
        polyjuice_effect = next((e for e in active_effects.get(member.id, {}).get("effects", [])
                                 if e.get("effect") == "polyjuice"), None)

        if polyjuice_effect:
            expires_at = datetime.fromisoformat(polyjuice_effect["expires_at"])
            # Check if the effect has expired. If it hasn't, the user is still in the cooldown period.
            if datetime.utcnow() < expires_at:
                remaining_time = expires_at - datetime.utcnow()
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return await ctx.send(f"You try to imbibe another Polyjuice, but can't get it down. ðŸ¤¢ You must wait {hours} hours, {minutes} minutes, and {seconds} seconds before you can drink it again.")

    # Bezoar (cleanse potions only)
    if pd["kind"] == "potion_bezoar":
        if member.id in active_effects:
            to_remove = [e["uid"] for e in active_effects[member.id]["effects"]
                         if (e.get("kind") or "").startswith("potion_") and e.get("effect") not in ("polyjuice", "polyfail_cat")]
            if len(to_remove) > 0:
                remove_galleons_local(caster.id, cost)
                for uid in to_remove:
                    await expire_effect(member, uid)
                await ctx.send(f"ðŸ§ª {caster.display_name} used Bezoar on {member.display_name}. Potion effects removed.")
            else:
                return await ctx.send("âŒ You can't use a Bezoar for that potion! No galleons have been taken.")
        else:
            return await ctx.send("âŒ You can't use a Bezoar for that potion! No galleons have been taken.")
        return

    # Polyjuice special-handling
    if pd["kind"] == "potion_polyjuice":
        remove_galleons_local(caster.id, cost) # Remove galleons for a successful polyjuice
        houses = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]
        chosen = random.choice(houses)
        user_house = get_user_house(member)
        if user_house == chosen:
            # Potion backfired since user already has the house role
            await apply_effect_to_member(member, "polyfail_cat", source="potion")
            await ctx.send(f"ðŸ§ª {caster.display_name} gave Polyjuice to {member.display_name}... it misfired! You get whiskers ðŸ± for 24 hours.")
        else:
            meta = {"polyhouse": chosen}
            await apply_effect_to_member(member, "polyjuice", source="potion", meta=meta)
            display_house = chosen.capitalize()
            await ctx.send(f"ðŸ§ª {caster.display_name} gave Polyjuice to {member.display_name} â€” you can access the **{display_house}** common room for 24 hours!")
        return

    # All other potions: permanent until finite/cleareffects
    remove_galleons_local(caster.id, cost)
    await apply_effect_to_member(member, potion, source="potion", meta={"permanent": True})
    await ctx.send(f"ðŸ§ª {caster.display_name} gave **{potion.capitalize()}** to {member.display_name}!")

# -------------------------
# COMMAND: CHOOSE (Room of Requirement)
# -------------------------
@bot.command()
async def choose(ctx, number: int):
    if ctx.channel.id != ROOM_OF_REQUIREMENT_ID:
        return await ctx.send(f"ðŸšª Please use this command in <#{ROOM_OF_REQUIREMENT_ID}>.")
    if number < 1 or number > 5:
        return await ctx.send("ðŸš« Pick a number between 1 and 5.")
    user_id = ctx.author.id
    if user_id not in active_potions:
        return await ctx.send("âŒ You donâ€™t have an active potion challenge. Cast Alohomora or drink a potion first.")
    if active_potions[user_id]["chosen"]:
        return await ctx.send("ðŸ§ª You already chose a potion for this challenge.")
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
        await ctx.send(f"ðŸŽ‰ {ctx.author.mention} picked potion {number} and won **100 galleons**!")
    else:
        await ctx.send(f"ðŸ’¨ {ctx.author.mention} picked potion {number}... nothing happened. Better luck next time!")
    await finalize_room_after_choice(ctx.author)
    del active_potions[user_id]

# -------------------------
# COMMAND: TRIGGER-GAME (testing) - restricted to Prefects/Head
# -------------------------
@bot.command(name="trigger-game", aliases=["trigger_game", "triggergame"])
async def trigger_game(ctx, member: discord.Member = None):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("âŒ You donâ€™t have permission to trigger the test game.")
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

    await ctx.send(f"ðŸ§ª Testing potion game started for {member.mention} (Prefects test).")

# -------------------------
# CLEAR EFFECTS COMMAND
# -------------------------

@bot.command(name="cleareffects")
async def cleareffects(ctx, member: discord.Member = None):
    if not is_staff_allowed(ctx.author):
        await ctx.send("Only Prefects and Heads of House can clear effects!")
        return

    target_member = member or ctx.author

    # Clear active effects from the user
    if target_member.id in active_effects:
        for e in list(active_effects[target_member.id]["effects"]):
            await remove_effect(target_member, e["uid"])
        await ctx.send(f"ðŸª„ All effects cleared for {target_member.display_name}.")
    else:
        await ctx.send(f"No active effects found for {target_member.display_name}.")

    # Clear the duel cooldown
    if target_member.id in duel_cooldowns:
        del duel_cooldowns[target_member.id]
        save_duel_cooldowns()
        await ctx.send(f"âš”ï¸ Duel cooldown has been cleared for {target_member.display_name}.")
    else:
        await ctx.send(f"No duel cooldown found for {target_member.display_name}.")

# -------------------------
# CLEAR ROOMS COMMAND
# -------------------------

@bot.command(name="clear")
async def clear_channel(ctx, limit: int = 100):
    """
    Clears messages from the Dueling Club or Room of Requirement channels.
    Only Prefects and Heads of House can use this command.
    """
    if not is_staff_allowed(ctx.author):
        await ctx.send("Only Prefects and Heads of House can clear channels!")
        return

    if ctx.channel.id not in [DUELING_CLUB_ID, ROOM_OF_REQUIREMENT_ID]:
        await ctx.send("This command can only be used in the Dueling Club or Room of Requirement.")
        return

    try:
        deleted = await ctx.channel.purge(limit=limit)
        await ctx.send(f"ðŸ§¹ Cleared {len(deleted)} messages from this channel.")
    except Exception as e:
        await ctx.send(f"An error occurred while trying to clear the channel: {e}")

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
    load_duel_cooldowns()

    guild = bot.get_guild(1398801863549259796)

    new_effects = {}

    # Rehydrate saved effects
    for uid, data in list(effects.items()):  # Use a copy to avoid modification issues
        member = guild.get_member(int(uid)) if guild else None
        if not member:
            continue
        
        # Check for the 'original_nick' key and set a default if not found
        original_nick = data.get("original_nick", member.display_name)

        active_effects[member.id] = {
            "original_nick": original_nick,
            "effects": []
        }

        for e in data.get("effects", []):
            try:
                if "expires_at" in e and e["expires_at"]:
                    exp_time = datetime.fromisoformat(e["expires_at"])
                    # Only reapply if still valid
                    if exp_time > datetime.utcnow():
                        active_effects[member.id]["effects"].append(e)
                        # Schedule expiry only for temporary ones
                        if e.get("kind") in ("potion_polyjuice", "role_alohomora"):
                            asyncio.create_task(schedule_expiry(member.id, e["uid"], exp_time))
                else:
                    # If there's no expiration date, assume it's a permanent effect and reapply
                    active_effects[member.id]["effects"].append(e)

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
        await owlry_channel.send("ðŸ¦‰ Hedwig is flying again!")

    print(f"[Hedwig] Logged in as {bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("âŒ DISCORD_TOKEN is missing from your .env file!")

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