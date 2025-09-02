import os
import re
import threading
from queue import Queue, Empty
import configparser
import discord
import time, random
import global_vars
from comms_journals import reply_to_sender
from misc_functions import execute_sendmoney_to_player
from occupations import execute_smuggle_for_player

# ----- Config loading -----
cfg = configparser.ConfigParser()
cfg.read('settings.ini')

# Raise error if Discord bot is misconfigured
BOT_TOKEN = (os.getenv('DISCORD_BOT_TOKEN') or cfg.get('DiscordBot', 'bot_token', fallback=None))
LISTEN_CHANNEL_ID = int(cfg.get('DiscordBot', 'listen_channel_id', fallback="0"))
CMD_PREFIX = cfg.get('DiscordBot', 'command_prefix', fallback='!')

if not BOT_TOKEN or not LISTEN_CHANNEL_ID:
    raise RuntimeError("You do not have permission to use this script. Speak to the Author")

print(f"[DiscordBridge] Config loaded. Channel: {LISTEN_CHANNEL_ID} | Prefix: '{CMD_PREFIX}'")

# Matches webhook text like: "In-Game Message from <sender> at ..."
FROM_PATTERN = re.compile(r"In-Game Message from\s+(.+?)\s+at\b", re.IGNORECASE)

# Work queue and worker thread
work_queue: Queue = Queue()

def worker():
    print("[DiscordBridge] Worker thread started.")
    while True:
        try:
            job = work_queue.get(timeout=1)
        except Empty:
            continue

        try:
            print(f"[DiscordBridge] Worker picked job: {job} | Queue size: {work_queue.qsize()}")

            ok = False
            action = job.get("action")

            # --- EXCLUSIVE BROWSER SECTION ---
            with global_vars.DRIVER_LOCK:  # NEW
                if action == "reply_to_sender":
                    ok = reply_to_sender(job["to"], job["text"])
                    print(f"[DiscordBridge] reply_to_sender -> {job['to']} | {'OK' if ok else 'FAILED'}")

                elif action == "smuggle":
                    ok = execute_smuggle_for_player(job["target"])
                    print(f"[DiscordBridge] smuggle -> {job['target']} | {'OK' if ok else 'FAILED'}")

                elif action == "sendmoney":
                    ok = execute_sendmoney_to_player(job["target"], job["amount"])
                    print(f"[DiscordBridge] sendmoney -> {job['target']} ${job['amount']} | {'OK' if ok else 'FAILED'}")

                else:
                    print(f"[DiscordBridge][WARN] Unknown action: {action}")
            # --- END EXCLUSIVE SECTION ---

            time.sleep(random.uniform(0.3, 0.9))

        except Exception as e:
            print(f"[DiscordBridge][ERROR] Worker exception: {e}")
        finally:
            work_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

# ----- Discord client -----
intents = discord.Intents.default()
intents.message_content = True  # Ensure Message Content Intent is enabled in your bot config
client = discord.Client(intents=intents)

def parse_tell(content: str):
    # !tell <player> <message...>
    parts = content.strip().split(maxsplit=2)
    if len(parts) < 3:
        return None, None
    _, player, msg = parts
    return player, msg

@client.event
async def on_ready():
    print(f"[DiscordBridge] Logged in as {client.user} ({client.user.id})")
    print(f"[DiscordBridge] Listening in channel id: {LISTEN_CHANNEL_ID}")

@client.event
async def on_message(message: discord.Message):
    # ignore our own messages
    if message.author == client.user:
        return

    # only listen in the configured channel
    if message.channel.id != LISTEN_CHANNEL_ID:
        return

    text = (message.content or "").strip()
    if not text:
        return

    # quick health check
    if text.lower() in {f"{CMD_PREFIX}ping", "!ping"}:
        await message.reply("pong")
        return

    # :smuggle <Player>  OR  !smuggle <Player>
    if text.startswith(":smuggle") or text.startswith(f"{CMD_PREFIX}smuggle"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Usage: `:smuggle <Player>` or `!smuggle <Player>`")
            return
        target = parts[1].strip()
        work_queue.put({"action": "smuggle", "target": target})
        print(f"[DiscordBridge] Queued smuggle for '{target}'. Queue size: {work_queue.qsize()}")
        await message.add_reaction("📦")
        await message.reply(f"Queued smuggle for **{target}**.")
        return

    # !sendmoney <Player> <Amount>
    if text.startswith(f"{CMD_PREFIX}sendmoney"):
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            await message.reply(f"Usage: `{CMD_PREFIX}sendmoney <player> <amount>`")
            return
        player = parts[1].strip()
        raw_amount = parts[2].strip()  # supports "100000", "100,000", "$100,000"
        digits = "".join(ch for ch in raw_amount if ch.isdigit())
        if not digits:
            await message.reply("Amount must contain digits (e.g., 100000 or $100,000).")
            print(f"[DiscordBridge][WARN] Bad amount '{raw_amount}' from {message.author}.")
            return
        amount_int = int(digits)

        work_queue.put({"action": "sendmoney", "target": player, "amount": amount_int})
        print(f"[DiscordBridge] Queued sendmoney: {player} <- {amount_int}. Queue size: {work_queue.qsize()}")
        await message.add_reaction("💸")
        await message.reply(f"Queued sendmoney: **{player}** ← ${amount_int:,}.")
        return

    # !tell <player> <message...>
    if text.startswith(f"{CMD_PREFIX}tell"):
        player, body = parse_tell(text)
        if not player or not body:
            await message.reply(f"Usage: `{CMD_PREFIX}tell <player> <message>`")
            return
        work_queue.put({"action": "reply_to_sender", "to": player, "text": body})
        print(f"[DiscordBridge] Queued tell -> {player}. Queue size: {work_queue.qsize()}")
        await message.add_reaction("📨")
        await message.reply(f"Queued reply to **{player}**.")
        return

    # Reply to a webhook alert (extract player from "In-Game Message from <Name> at ...")
    if message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved  # type: ignore
        if isinstance(ref_msg, discord.Message):
            m = FROM_PATTERN.search(ref_msg.content or "")
            if m:
                player = m.group(1).strip()
                work_queue.put({"action": "reply_to_sender", "to": player, "text": text})
                print(f"[DiscordBridge] Queued threaded reply -> {player}. Queue size: {work_queue.qsize()}")
                await message.add_reaction("📨")
                await message.reply(f"Queued reply to **{player}**.")
                return

    # Use the help feature to get commands
    if text in {f"{CMD_PREFIX}help", f"{CMD_PREFIX}commands"}:
        await message.reply(
            "Commands:\n"
            f"- `{CMD_PREFIX}tell <player> <message>`\n"
            f"- `:smuggle <player>` or `{CMD_PREFIX}smuggle <player>`\n"
            f"- `{CMD_PREFIX}sendmoney <player> <amount>`\n"
            f"- `{CMD_PREFIX}ping`"
        )

def run_discord_bot():
    print("[DiscordBridge] Starting Discord client...")
    client.run(BOT_TOKEN)

def start_discord_bridge():
    t = threading.Thread(target=run_discord_bot, daemon=True)
    t.start()
    print("[DiscordBridge] Thread launched.")
    return t

if __name__ == "__main__":
    start_discord_bridge()