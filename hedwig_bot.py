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

# Dueling
duels = {}
DUEL_TIMER = 30
DUEL_REACTIONS = ["🛡️", "⚔️"]
DUELLISTS = ["duelist_one", "duelist_two"]

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
    "hufflepuff": "<:hufflepuff:1409203862757310534>",
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
        "cost": 20,
        "kind": "nickname",
        "prefix": "<:aguamenti:1415595031644999742>",
        "prefix_unicode": "🌊",
        "suffix": "<:aguamenti:1415595031644999742>",
        "suffix_unicode": "🌊",
        "description": "Surrounds the target's nickname with water."
    },
    "confundo": {
        "cost": 25,
        "kind": "nickname",
        "prefix": "<:confundo:1415595034769625199>",
        "prefix_unicode": "❓CONFUNDED - ",
        "suffix": "",
        "suffix_unicode": "❓",
        "description": "Prefixes CONFUNDED to the target's nickname."
    },
    "diffindo": {
        "cost": 30,
        "kind": "truncate",
        "length": 5,
        "description": "Removes the last 5 characters of the target's nickname."
    },
    "ebublio": {
        "cost": 20,
        "kind": "nickname",
        "prefix": "<:ebublio:1415595038397693982>",
        "prefix_unicode": "🫧",
        "suffix": "<:ebublio:1415595038397693982>",
        "suffix_unicode": "🫧",
        "description": "Surrounds the target's nickname with bubbles."
    },
    "herbifors": {
        "cost": 20,
        "kind": "nickname",
        "prefix": "<:herbifors:1415595039882481674>",
        "prefix_unicode": "🌸",
        "suffix": "<:herbifors:1415595039882481674>",
        "suffix_unicode": "🌸",
        "description": "Gives the target a floral nickname."
    },
    "serpensortia": {
        "cost": 20,
        "kind": "nickname",
        "prefix": "<:serpensortia:1415595048124289075>",
        "prefix_unicode": "🐍",
        "suffix": "<:serpensortia:1415595048124289075>",
        "suffix_unicode": "🐍",
        "description": "Surrounds the target's nickname with snake emojis."
    },
    "tarantallegra": {
        "cost": 20,
        "kind": "nickname",
        "prefix": "<:tarantallegra:1415595049411936296>",
        "prefix_unicode": "💃",
        "suffix": "<:tarantallegra:1415595049411936296>",
        "suffix_unicode": "💃",
        "description": "Surrounds the target's nickname with dancing emojis."
    },
    "alohomora": {
        "cost": 20,
        "kind": "role",
        "role": ALOHOMORA_ROLE_NAME,
        "description": "Gives the target the 'Alohomora' role for a short period."
    },
    "lumos": {
        "cost": 20,
        "kind": "role",
        "role_id": ROLE_IDS["lumos"],
        "description": "Gives the target the 'Lumos' role for a short period."
    },
    "incendio": {
        "cost": 30,
        "kind": "nickname",
        "prefix": "<:incendio:1415595041191235718> ",
        "prefix_unicode": "🔥",
        "suffix": " <:incendio:1415595041191235718>",
        "suffix_unicode": "🔥",
        "description": "Surrounds the target's nickname with fire."
    },
}


# -------------------------
# BOT EVENTS
# -------------------------

@bot.event
async def on_ready():
    """Bot initialization event."""
    print(f"[Hedwig] Logged in as {bot.user}")

    # Load data from disk
    load_galleons()
    load_house_points()
    load_effects()

    # Restore all active effects from disk
    new_effects = {}
    for uid, data in effects.items():
        member = get_member_from_id(int(uid))
        if not member:
            print(f"user {uid} not found. skipping effect restoration.")
            continue
        try:
            # Reapply all effects to the user from the saved state.
            for e in data.get("effects", []):
                await add_effect(member, e["effect"], restore=True, uid=e["uid"])
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

    cleanup_effects.start()
    await bot.change_presence(activity=discord.Game(name="with spells! Type !help"))


# -------------------------
# Dueling Functionality
# -------------------------
def find_user_by_mention(guild, mention_str):
    """Find a member in the guild by their mention string."""
    try:
        user_id = int(mention_str.replace('<@', '').replace('>', '').replace('!', ''))
        return guild.get_member(user_id)
    except (ValueError, IndexError):
        return None

async def start_duel(ctx, opponent):
    if duels.get(ctx.author.id) or duels.get(opponent.id):
        await ctx.send("One of you is already in a duel! Please finish it first.")
        return False
    if ctx.author.id == opponent.id:
        await ctx.send("You can't duel yourself!")
        return False

    duel_id = uuid.uuid4().hex
    duels[duel_id] = {
        "players": [ctx.author.id, opponent.id],
        "messages": [],
        "channel": ctx.channel.id,
        "expires_at": time.time() + DUEL_TIMER,
        "winner": None
    }
    duels[ctx.author.id] = duel_id
    duels[opponent.id] = duel_id
    return True

async def end_duel(duel_id):
    duel = duels.get(duel_id)
    if not duel:
        return

    # Clean up from the global state
    for player_id in duel["players"]:
        duels.pop(player_id, None)
    duels.pop(duel_id, None)

    # Clean up messages
    channel = bot.get_channel(duel["channel"])
    if channel:
        for msg_id in duel["messages"]:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except discord.NotFound:
                continue

async def handle_duel_message(message):
    duel_id = duels.get(message.author.id)
    if not duel_id:
        return

    duel = duels[duel_id]
    if message.channel.id != duel["channel"]:
        return

    if message.author.id not in duel["players"]:
        return

    duel["messages"].append(message.id)
    duel["expires_at"] = time.time() + DUEL_TIMER


@bot.command(name="duel")
async def duel(ctx, opponent_mention=None):
    if ctx.channel.id != DUELING_CLUB_ID:
        await ctx.send(f"Duels must take place in the Dueling Club channel! <#{DUELING_CLUB_ID}>")
        return

    if not opponent_mention:
        await ctx.send("You must mention someone to duel! e.g. `!duel @user`")
        return

    opponent = find_user_by_mention(ctx.guild, opponent_mention)
    if not opponent:
        await ctx.send("That user wasn't found.")
        return

    if not await start_duel(ctx, opponent):
        return

    duel_id = duels[ctx.author.id]
    p1 = ctx.author
    p2 = opponent

    msg = await ctx.send(f"A duel has been initiated between {p1.mention} and {p2.mention}!")
    duels[duel_id]["messages"].append(msg.id)

    # Initial prompt
    msg = await ctx.send(f"⚔️ {p1.mention} and {p2.mention}, react to this message to cast your spell! First to react wins!")
    duels[duel_id]["messages"].append(msg.id)

    def check(reaction, user):
        return user.id in duel["players"] and str(reaction.emoji) in DUEL_REACTIONS

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=DUEL_TIMER, check=check)
        winner = user
        loser = p1 if winner == p2 else p2

        # Winner gets a random effect and galleons
        effect_name, effect_info = random.choice(list(EFFECT_LIBRARY.items()))
        await add_effect(winner, effect_name)
        add_galleons_local(winner.id, 50)
        await ctx.send(f"⚡ {winner.mention} casts a spell and wins the duel! They have been awarded 50 galleons and the **{effect_name.title()}** effect! 🪄")
        await end_duel(duel_id)

    except asyncio.TimeoutError:
        await ctx.send("Duel timed out! No one won.")
        await end_duel(duel_id)

    except Exception as e:
        print(f"Error in duel: {e}")
        await ctx.send("An unexpected error occurred during the duel.")
        await end_duel(duel_id)


# -------------------------
# EFFECT FUNCTIONALITY
# -------------------------

async def add_effect(member: discord.Member, effect_name: str, duration: timedelta = timedelta(minutes=15), restore: bool = False, uid: str = None):
    """Applies a spell effect to a member."""
    if not uid:
        uid = make_effect_uid()

    effect = EFFECT_LIBRARY.get(effect_name)
    if not effect:
        return

    if member.id not in active_effects:
        active_effects[member.id] = {
            "original_nick": member.display_name,
            "effects": []
        }
    
    current_effects = active_effects[member.id]["effects"]
    current_effects.append({
        "effect": effect_name,
        "expires_at": (now_utc() + duration).isoformat(),
        "uid": uid
    })
    
    effects[str(member.id)] = active_effects[member.id]
    save_effects()

    kind = effect.get("kind")
    if kind == "nickname":
        # Apply the visual nickname effect
        new_nick = active_effects[member.id]["original_nick"]
        prefix = effect.get("prefix_unicode", "")
        suffix = effect.get("suffix_unicode", "")
        new_nick = f"{prefix}{new_nick}{suffix}"
        
        await set_nickname(member, new_nick)
    
    elif kind == "role":
        # Apply the role effect
        role_name = effect.get("role")
        role_id = effect.get("role_id")
        
        role = discord.utils.get(member.guild.roles, id=role_id)
        if not role and role_name:
            role = discord.utils.get(member.guild.roles, name=role_name)
        
        if role:
            await safe_add_role(member, role)
            
    elif kind == "truncate":
        original_nick = active_effects[member.id]["original_nick"]
        length = effect.get("length", 1)
        new_nick = original_nick[:-length]
        await set_nickname(member, new_nick)

async def remove_effect(member: discord.Member, uid: str):
    """Removes a specific effect and reverts a member's name/roles if no other effects remain."""
    if member.id not in active_effects:
        return

    user_effects = active_effects[member.id]["effects"]
    user_effects = [e for e in user_effects if e["uid"] != uid]
    active_effects[member.id]["effects"] = user_effects

    # Check if there are any effects left
    if not user_effects:
        # No more effects, revert to original nickname and remove special roles
        try:
            await set_nickname(member, active_effects[member.id]["original_nick"])
        except Exception as e:
            print(f"Could not restore original nickname for {member}: {e}")

        # Revert special roles
        for role_id in (ROLE_IDS["lumos"], ROLE_IDS["amortentia"]):
            role = discord.utils.get(member.guild.roles, id=role_id)
            if role:
                await safe_remove_role(member, role)
        
        # Remove the alohomora role if it exists
        alohomora_role = discord.utils.get(member.guild.roles, name=ALOHOMORA_ROLE_NAME)
        if alohomora_role:
            await safe_remove_role(member, alohomora_role)

        # Clean up the in-memory state
        del active_effects[member.id]
        
    save_effects()


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
            effects.pop(uid, None)
        else:
            data["effects"] = new_effects

    if expired:
        save_effects()

    for user_id, effect_uid in expired:
        member = get_member_from_id(int(user_id))
        if member:
            await remove_effect(member, effect_uid)
            print(f"Removed expired effect {effect_uid} from {member.display_name}")


# -------------------------
# BOT STARTUP
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN is missing from your .env file!")

bot.run(TOKEN)