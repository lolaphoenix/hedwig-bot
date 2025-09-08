# hedwig_bot.py
import os
import random
import asyncio
import uuid
import discord
from discord.ext import commands
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
# Name-based role for Alohomora (you said this role exists by name)
ALOHOMORA_ROLE_NAME = "Alohomora"

# Potion emojis (raw custom emoji strings you provided)
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


# -------------------------
# STATE (IN-MEMORY)
# -------------------------
# NOTE: All state is in-memory. Restarting the bot clears balances, active effects, cooldowns.
house_points = {h: 0 for h in house_emojis}             # house -> points
galleons = {}                                           # user_id -> int
last_daily = {}                                         # user_id -> datetime

# Active effects (spells & potions) per user:
# user_id -> { "original_nick": str, "effects": [ {uid, name, kind, expires_at, meta...}, ... ] }
active_effects = {}

# Cooldowns / restrictions
alohomora_cooldowns = {}    # target_user_id -> datetime of last Alohomora
silencio_last = {}          # target_user_id -> datetime of last Silencio (weekly limit)
silenced_until = {}         # user_id -> datetime until which they are silenced

# Active potion-specific data (if you prefer separate tracking)
# e.g. active_potion_effects[user_id] = {"luck": 0.5, "expires_at": dt}
active_potion_effects = {}

# -------------------------
# HELPERS
# -------------------------
def now_utc():
    return datetime.utcnow()

def is_staff_allowed(member: discord.Member) -> bool:
    """Return True if member has either Prefects or Head of House role."""
    allowed_ids = {ROLE_IDS["prefects"], ROLE_IDS["head_of_house"]}
    return any(r.id in allowed_ids for r in member.roles)

def get_member_from_id(user_id: int):
    """Search all guilds for the member (works if bot is only in one guild or has access)."""
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
    return galleons.get(user_id, 0)

def add_galleons_local(user_id: int, amount: int):
    galleons[user_id] = get_balance(user_id) + amount

def remove_galleons_local(user_id: int, amount: int):
    galleons[user_id] = max(0, get_balance(user_id) - amount)

def make_effect_uid() -> str:
    return uuid.uuid4().hex

# -------------------------
# EFFECT DEFINITIONS
# -------------------------
# Each effect is represented when applied by a dict put into active_effects[user]['effects'].
# "kind" determines how we apply/undo it.
EFFECT_LIBRARY = {
    # spells
    "aguamenti": {"cost": 20, "kind": "nickname", "prefix": "🌊", "suffix": "🌊", "duration": 86400},
    "confundo": {"cost": 25, "kind": "nickname", "prefix": "❓CONFUNDED - ", "suffix": "", "duration": 86400},
    "diffindo": {"cost": 30, "kind": "truncate", "length": 5, "duration": 86400},
    "ebublio": {"cost": 20, "kind": "nickname", "prefix": "🫧", "suffix": "🫧", "duration": 86400},
    "herbifors": {"cost": 20, "kind": "nickname", "prefix": "🌸", "suffix": "🌸", "duration": 86400},
    "locomotorwibbly": {"cost": 20, "kind": "nickname", "prefix": "🍮", "suffix": "🍮", "duration": 86400},
    "serpensortia": {"cost": 20, "kind": "nickname", "prefix": "🐍", "suffix": "🐍", "duration": 86400},
    "tarantallegra": {"cost": 20, "kind": "nickname", "prefix": "💃", "suffix": "💃", "duration": 86400},
    "incendio": {"cost": 25, "kind": "nickname", "prefix": "🔥", "suffix": "🔥", "duration": 86400},
    "silencio": {"cost": 40, "kind": "silence", "duration": 86400, "weekly_limit_days": 7},
    "alohomora": {"cost": 50, "kind": "role_alohomora", "duration": 86400},
    "lumos": {"cost": 15, "kind": "role_lumos", "prefix": "⭐", "duration": 86400},
    # (you can add more)
}

POTION_LIBRARY = {
    "felixfelicis": {"cost": 60, "kind": "potion_luck_good", "prefix": "🍀", "duration": 86400},
    "draughtlivingdeath": {"cost": 50, "kind": "potion_luck_bad", "prefix": "💀", "duration": 86400},
    "amortentia": {"cost": 70, "kind": "potion_amortentia", "prefix": "💖", "role_id": ROLE_IDS["amortentia"], "duration": 86400},
    "polyjuice": {"cost": 80, "kind": "potion_polyjuice", "duration": 86400},
    "bezoar": {"cost": 30, "kind": "potion_bezoar", "duration": 0},
}

# -------------------------
# APPLY / REMOVE EFFECTS
# -------------------------
async def apply_effect_to_member(member: discord.Member, effect_name: str, source: str = "spell"):
    """
    Apply an effect to member, register it in active_effects and schedule expiration.
    `source` is "spell" or "potion" for informational messages/scheduling.
    """
    uid = make_effect_uid()
    now = now_utc()

    # Determine effect definition (spell or potion)
    if effect_name in EFFECT_LIBRARY:
        ed = EFFECT_LIBRARY[effect_name].copy()
    elif effect_name in POTION_LIBRARY:
        ed = POTION_LIBRARY[effect_name].copy()
    else:
        print("Unknown effect:", effect_name)
        return

    duration = ed.get("duration", 86400)
    expires_at = now + timedelta(seconds=duration) if duration > 0 else None

    entry = {
        "uid": uid,
        "name": effect_name,
        "kind": ed.get("kind"),
        "prefix": ed.get("prefix"),
        "suffix": ed.get("suffix"),
        "length": ed.get("length"),
        "role_id": ed.get("role_id"),
        "expires_at": expires_at,
        "applied_at": now,
        "source": source,
    }

    # Store original nick if first effect for this user
    if member.id not in active_effects:
        active_effects[member.id] = {"original_nick": member.display_name, "effects": []}

    active_effects[member.id]["effects"].append(entry)

    # Do immediate application for role effects or silencing etc.
    kind = entry["kind"]

    if kind == "role_alohomora":
        # find role by name first
        guild_role = None
        for g in bot.guilds:
            if g.get_member(member.id):
                guild_role = discord.utils.get(g.roles, name=ALOHOMORA_ROLE_NAME)
                break
        if guild_role:
            await safe_add_role(member, guild_role)
    elif kind == "role_lumos":
        role = None
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = g.get_role(ROLE_IDS["lumos"])
                break
        if role:
            await safe_add_role(member, role)
    elif kind == "potion_amortentia":
        # add role
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = g.get_role(entry["role_id"])
                if role:
                    await safe_add_role(member, role)
                break
    elif kind == "potion_polyjuice":
        # assign a random house role for 24h
        houses = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]
        chosen = random.choice(houses)
        role_id = ROLE_IDS[chosen]
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = g.get_role(role_id)
                if role:
                    await safe_add_role(member, role)
                    # record which house we gave so we can remove later
                    entry["polyhouse"] = chosen
                break
    elif kind == "silence":
        # silence user: prevent casting for duration
        silenced_until[member.id] = entry["expires_at"]

    # For nickname-affecting kinds we will recompute the nickname from original + all effects
    await recompute_nickname(member)

    # schedule removal if needed
    if entry["expires_at"]:
        asyncio.create_task(schedule_expiry(member.id, uid, entry["expires_at"]))

    return uid

async def schedule_expiry(user_id: int, uid: str, expires_at: datetime):
    """Wait until expires_at and then remove effect uid for user_id."""
    delta = (expires_at - now_utc()).total_seconds()
    if delta > 0:
        await asyncio.sleep(delta)
    # After sleeping, try to remove the effect (if still present)
    member = get_member_from_id(user_id)
    if member:
        await expire_effect(member, uid)
    else:
        # Try to still remove from state if member not found (cleanup)
        if user_id in active_effects:
            # remove effect entry by uid
            effects = active_effects[user_id]["effects"]
            newlist = [e for e in effects if e["uid"] != uid]
            active_effects[user_id]["effects"] = newlist
            if not newlist:
                del active_effects[user_id]

async def expire_effect(member: discord.Member, uid: str):
    """Remove an effect by uid from a member and update roles/nicknames."""
    data = active_effects.get(member.id)
    if not data:
        return
    effects = data["effects"]
    found = None
    for e in effects:
        if e["uid"] == uid:
            found = e
            break
    if not found:
        return

    effects.remove(found)

    # undo immediate things depending on kind
    kind = found["kind"]
    if kind == "role_alohomora":
        # remove Alohomora role
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = discord.utils.get(g.roles, name=ALOHOMORA_ROLE_NAME)
                if role and role in member.roles:
                    await safe_remove_role(member, role)
                break
    elif kind == "role_lumos":
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = g.get_role(ROLE_IDS["lumos"])
                if role and role in member.roles:
                    await safe_remove_role(member, role)
                break
    elif kind == "potion_amortentia":
        for g in bot.guilds:
            m = g.get_member(member.id)
            if m:
                role = g.get_role(entry.get("role_id")) if (entry := found) else None
                if role and role in member.roles:
                    await safe_remove_role(member, role)
                break
    elif kind == "potion_polyjuice":
        # remove the polyhouse role if present
        polyhouse = found.get("polyhouse")
        if polyhouse:
            role_id = ROLE_IDS.get(polyhouse)
            for g in bot.guilds:
                m = g.get_member(member.id)
                if m:
                    role = g.get_role(role_id)
                    if role and role in member.roles:
                        await safe_remove_role(member, role)
                    break
    elif kind == "silence":
        # remove from silenced map
        silenced_until.pop(member.id, None)

    # recompute nickname (restore to original when no effects)
    if effects:
        await recompute_nickname(member)
    else:
        # restore original nick
        orig = data.get("original_nick", None)
        if orig is None:
            orig = member.display_name
        try:
            await member.edit(nick=orig)
        except Exception:
            pass
        # cleanup
        del active_effects[member.id]

# nickname composition: starting from original nick, apply effects in order of application
async def recompute_nickname(member: discord.Member):
    data = active_effects.get(member.id)
    if not data:
        return
    base = data.get("original_nick", member.display_name)
    # apply effects in order
    for e in data["effects"]:
        kind = e["kind"]
        if kind == "nickname":
            prefix = e.get("prefix", "")
            suffix = e.get("suffix", "")
            base = f"{prefix}{base}{suffix}"
        elif kind == "truncate":
            length = e.get("length", 0)
            if length and len(base) > length:
                base = base[:-length]
        elif kind == "role_lumos":
            # lumos has a prefix optionally
            prefix = e.get("prefix", "")
            base = f"{prefix}{base}"
        elif kind == "silence":
            prefix = "🤫"
            base = f"{prefix}{base}"
        elif kind and kind.startswith("potion_"):
            # potion prefix if present
            prefix = e.get("prefix", "")
            if prefix:
                base = f"{prefix}{base}"
        # other kinds can be added here
    # set nick
    await set_nickname(member, base)

# -------------------------
# ROOM / ALOHOMORA GAME HELPERS
# -------------------------
def pick_winning_potion():
    return random.randint(1, 5)

async def announce_room_for(member: discord.Member):
    """Send welcome and big potion emojis in separate messages so emojis appear jumbo."""
    room = bot.get_channel(ROOM_OF_REQUIREMENT_ID)
    if not room:
        return
    await room.send(f"🔮 Welcome {member.mention}!\nPick a potion with `!choose 1-5`")
    # send emojis on their own line (renders larger)
    await room.send(" ".join(POTION_EMOJIS))

# After a player chooses, we remove Alohomora role and schedule purge after 30 min
async def finalize_room_after_choice(member: discord.Member):
    # remove Alohomora role immediately
    for g in bot.guilds:
        m = g.get_member(member.id)
        if m:
            role = discord.utils.get(g.roles, name=ALOHOMORA_ROLE_NAME)
            if role and role in m.roles:
                await safe_remove_role(m, role)
            break
    # schedule purge after 30 minutes
    await asyncio.create_task(purge_room_after_delay(1800))

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
        "🦉 **Hedwig Help** 🦉\n\n"
        "✨ Student Commands:\n"
        "`!shop` — View spells & potions\n"
        "`!cast <spell> @user` — Cast a spell on a user (spells cost galleons)\n"
        "`!drink <potion> [@user]` — Drink a potion or give to someone\n"
        "`!balance` — Check your galleons\n"
        "`!daily` — Collect daily pocket money\n"
        "`!points` — Show house points\n"
        "`!choose <1-5>` — Choose a potion in the Room of Requirement\n"
    )
    await ctx.send(msg)

@bot.command()
async def hedwigmod(ctx):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to see mod commands.")
    msg = (
        "⚖️ **Hedwig Moderator Commands** ⚖️\n"
        "`!addpoints <house> <points>` — Add house points\n"
        "`!resetpoints` — Reset house points\n"
        "`!givegalleons @user <amount>` — Give galleons to a user (Prefects & Head of House only)\n"
        "`!resetgalleons` — Clear all galleon balances\n"
    )
    await ctx.send(msg)

# -------------------------
# COMMANDS: HOUSE POINTS
# -------------------------
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
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to reset points.")
    for house in house_points:
        house_points[house] = 0
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
    """Prefects and Head of House only"""
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
    await ctx.send("🔄 All galleon balances have been reset.")

@bot.command()
async def leaderboard(ctx):
    if not galleons:
        return await ctx.send("No one has any galleons yet!")
    sorted_balances = sorted(galleons.items(), key=lambda x: x[1], reverse=True)[:10]
    result = "🏦 Gringotts Rich List 🏦\n"
    for i, (user_id, bal) in enumerate(sorted_balances, start=1):
        member = get_member_from_id(user_id) or ctx.guild.get_member(user_id)
        name = member.display_name if member else f"User {user_id}"
        result += f"{i}. {name} — {bal} galleons\n"
    await ctx.send(result)

# -------------------------
# COMMAND: SHOP (spells + potions)
# -------------------------
@bot.command()
async def shop(ctx):
    msg = "🪄 **Spell Shop** 🪄\n"
    for k, v in EFFECT_LIBRARY.items():
        msg += f"**{k.capitalize()}** — {v.get('cost', '?')} galleons: {v.get('kind')} — {v.get('description','')}\n"
    msg += "\n🍷 **Potion Shop** 🍷\n"
    for k, v in POTION_LIBRARY.items():
        msg += f"**{k.capitalize()}** — {v.get('cost', '?')} galleons: {v.get('description','')}\n"
    await ctx.send(msg)

# -------------------------
# COMMAND: CAST (spells)
# -------------------------
@bot.command()
async def cast(ctx, spell: str, member: discord.Member):
    caster = ctx.author
    spell = spell.lower()

    # check silence on caster
    if caster.id in silenced_until and now_utc() < silenced_until[caster.id]:
        return await ctx.send("🤫 You are silenced and cannot cast spells right now.")

    # validate spell
    if spell not in EFFECT_LIBRARY:
        return await ctx.send("❌ That spell doesn’t exist. Check the shop with `!shop`.")

    ed = EFFECT_LIBRARY[spell]
    cost = ed.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("💸 You don’t have enough galleons to cast that spell!")

    # Silencio weekly limit for target
    if spell == "silencio":
        now = now_utc()
        last = silencio_last.get(member.id)
        if last and now - last < timedelta(days=7):
            return await ctx.send("⏳ Silencio can only be cast on this user once per week.")
        silencio_last[member.id] = now

    # Alohomora cooldown for target (24h)
    if spell == "alohomora":
        now = now_utc()
        last = alohomora_cooldowns.get(member.id)
        if last and now - last < timedelta(hours=24):
            return await ctx.send("⏳ Alohomora can only be cast on this user once every 24 hours.")
        alohomora_cooldowns[member.id] = now

    # Deduct cost and apply
    remove_galleons_local(caster.id, cost)
    await apply_effect_to_member(member, spell, source="spell")

    await ctx.send(f"✨ {caster.display_name} cast **{spell.capitalize()}** on {member.display_name}!")

    # Additional behavior: if Alohomora start potion game
    if spell == "alohomora":
        # make winning pick and store
        active_potions[member.id] = {"winning": pick_winning_potion(), "chosen": False, "started_by": caster.id}
        await announce_room_for(member)

# -------------------------
# COMMAND: DRINK (potions)
# -------------------------
@bot.command()
async def drink(ctx, potion: str, member: discord.Member = None):
    potion = potion.lower()
    member = member or ctx.author
    caster = ctx.author

    if potion not in POTION_LIBRARY:
        return await ctx.send("❌ That potion doesn’t exist. Check the shop with `!shop`.")

    pd = POTION_LIBRARY[potion]
    cost = pd.get("cost", 0)
    if get_balance(caster.id) < cost:
        return await ctx.send("💸 You don’t have enough galleons to buy that potion!")

    remove_galleons_local(caster.id, cost)

    # Bezoar (cleanse) is handled specially
    if pd["kind"] == "potion_bezoar":
        # remove potion effects and roles (amortentia, polyjuice)
        # remove any amortentia/amort role and polyhouse role and remove potion-prefix effects
        # simply remove effects whose kind begins with 'potion_'
        if member.id in active_effects:
            to_remove = [e["uid"] for e in active_effects[member.id]["effects"] if (e["kind"] or "").startswith("potion_")]
            for uid in to_remove:
                await expire_effect(member, uid)
        await ctx.send(f"🧪 {caster.display_name} used Bezoar on {member.display_name}. Potion effects removed.")
        return

    # Apply potion effect (treat same as effect)
    await apply_effect_to_member(member, potion, source="potion")
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
    # check for potion luck effects via active_effects
    luck = 0.0
    data = active_effects.get(user_id)
    if data:
        for e in data["effects"]:
            if e["name"] == "felixfelicis" or e["name"] == "felixf":
                luck += 0.5
            if e["name"] == "draughtlivingdeath" or e["name"] == "livingdeath":
                luck -= 0.5

    # chance overrides
    forced_win = (luck > 0 and random.random() < luck)
    forced_miss = (luck < 0 and random.random() < abs(luck))

    final_choice = number
    if forced_win:
        final_choice = winning
    elif forced_miss:
        # make final_choice something other than winning
        opts = [i for i in range(1, 6) if i != winning]
        final_choice = random.choice(opts)

    if final_choice == winning:
        add_galleons_local(user_id, 100)
        await ctx.send(f"🎉 {ctx.author.mention} picked potion {number} and won **100 galleons**!")
    else:
        await ctx.send(f"💨 {ctx.author.mention} picked potion {number}... nothing happened. Better luck next time!")

    # remove Alohomora role and schedule purge in 30 minutes (do not remove potion effects here)
    await finalize_room_after_choice(ctx.author)

    # cleanup this user's active_potions entry
    del active_potions[user_id]

# -------------------------
# COMMAND: TRIGGER-GAME (testing) - restricted to Prefects/Head
# -------------------------
@bot.command(name="trigger-game", aliases=["trigger_game", "triggergame"])
async def trigger_game(ctx, member: discord.Member = None):
    if not is_staff_allowed(ctx.author):
        return await ctx.send("❌ You don’t have permission to trigger the test game.")
    member = member or ctx.author
    active_potions[member.id] = {"winning": pick_winning_potion(), "chosen": False, "started_by": ctx.author.id}
    await announce_room_for(member)
    await ctx.send(f"🧪 Testing potion game started for {member.mention} (Prefects test).")

# -------------------------
# COMMAND: FINITE
# -------------------------
@bot.command()
async def finite(ctx, member: discord.Member, effect_name: str = None):
    """
    Remove the last applied effect or a specific effect by name.
    Usage: !finite @user       -> removes last effect
           !finite @user name  -> removes the most recent effect with that name
    """
    if member.id not in active_effects:
        return await ctx.send("No active spells/potions on this user.")

    effects = active_effects[member.id]["effects"]
    if effect_name:
        # remove most recent matching
        idx = None
        for i in range(len(effects)-1, -1, -1):
            if effects[i]["name"] == effect_name.lower():
                idx = i
                break
        if idx is None:
            return await ctx.send("That effect was not found on the user.")
        uid = effects[idx]["uid"]
        await expire_effect(member, uid)
        return await ctx.send(f"✨ Removed **{effect_name}** from {member.display_name}.")
    else:
        # remove last effect
        last = effects[-1]
        uid = last["uid"]
        await expire_effect(member, uid)
        return await ctx.send(f"✨ Removed the most recent effect from {member.display_name}.")

# -------------------------
# STARTUP / RUN
# -------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} connected as Hedwig — ready to serve the wizarding community!")

# -------------------------
# Run the bot
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in environment (.env)")

bot.run(TOKEN)
