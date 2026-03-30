import discord
import re
import os
import asyncio
from pathlib import Path
from discord.ext import commands, tasks

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"

# Map of original domains to embed-friendly domains
URL_REPLACEMENTS = {
    "instagram.com": "kkinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "facebook.com": "facebed.app",
    "tiktok.com": "vxtiktok.com",
    "reddit.com": "rxddit.com",
}

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# Health check heartbeat task
@tasks.loop(seconds=30)
async def update_heartbeat():
    """Updates a file timestamp so Docker healthcheck knows the bot is alive."""
    try:
        Path(HEARTBEAT_FILE).touch()
    except Exception as e:
        print(f"Heartbeat error: {e}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if not update_heartbeat.is_running():
        update_heartbeat.start()
    print("Link Fixer is active and heartbeat started.")

@bot.event
async def on_message(message):
    # Ignore bot's own messages to prevent loops
    if message.author == bot.user:
        return

    content = message.content
    new_content = content
    found_match = False

    # Scan and replace domains
    for domain, replacement in URL_REPLACEMENTS.items():
        if domain in new_content:
            # Case-insensitive replacement of the domain
            pattern = re.compile(re.escape(domain), re.IGNORECASE)
            new_content = pattern.sub(replacement, new_content)
            found_match = True

    if found_match:
        try:
            # Post the corrected link and credit the original user
            credit_text = f"Shared by: **{message.author.display_name}**\n{new_content}"
            await message.channel.send(credit_text)
            
            # Remove the original message
            await message.delete()
        except Exception as e:
            print(f"Error handling message from {message.author.name}: {e}")

if __name__ == "__main__":
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token = f.read().strip()
        
        try:
            bot.run(token)
        except Exception as e:
            print(f"Fatal connection error: {e}")
    else:
        print(f"CRITICAL: {TOKEN_FILE} not found in /app/")
