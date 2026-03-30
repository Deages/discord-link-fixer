import discord
import re
import os
import asyncio
from pathlib import Path
from discord.ext import commands, tasks

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"

URL_REPLACEMENTS = {
    "instagram.com": "kkinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "facebook.com": "facebed.app",
}

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# Health check heartbeat task
@tasks.loop(seconds=30)
async def update_heartbeat():
    """Updates a file timestamp so Docker knows the bot is alive."""
    Path(HEARTBEAT_FILE).touch()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    update_heartbeat.start()
    print("Heartbeat service started.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content
    new_content = content
    found_match = False

    for domain, replacement in URL_REPLACEMENTS.items():
        if domain in new_content:
            # Matches domain while ensuring it's not part of another word
            pattern = re.compile(re.escape(domain), re.IGNORECASE)
            new_content = pattern.sub(replacement, new_content)
            found_match = True

    if found_match:
        try:
            # Credit the user by nickname without tagging/pinging
            credit_text = f"Shared by: **{message.author.display_name}**\n{new_content}"
            await message.channel.send(credit_text)
            await message.delete()
        except Exception as e:
            print(f"Error handling message: {e}")

if __name__ == "__main__":
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
            bot.run(token)
        else:
            print(f"Error: {TOKEN_FILE} not found.")
    except Exception as e:
        print(f"Fatal Error: {e}")
