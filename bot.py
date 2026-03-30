import discord
import re
import os
import asyncio
from pathlib import Path
from discord.ext import commands, tasks

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"

# Domain mapping for embed-friendly replacements
URL_REPLACEMENTS = {
    "instagram.com": "kkinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "facebook.com": "facebed.app",
    "tiktok.com": "vxtiktok.com",
    "reddit.com": "rxddit.com",
}

# Regex patterns for paths that usually indicate a video or media post.
# This ensures the bot only triggers on content, not profile links.
MEDIA_PATTERNS = {
    "instagram.com": [r"/reels?/", r"/p/", r"/tv/"],
    "tiktok.com": [r"/video/", r"/v/", r"/t/"],
    "twitter.com": [r"/status/"],
    "x.com": [r"/status/"],
    "facebook.com": [r"/videos?/", r"/reel/", r"/watch/", r"story\.php"],
    "reddit.com": [r"/comments/"],
    "bsky.app": [r"/post/"],
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
    print("Link Fixer is active with Video-Path filtering.")

@bot.event
async def on_message(message):
    # Ignore bot's own messages to prevent loops
    if message.author == bot.user:
        return

    content = message.content
    new_content = content
    found_match = False

    # Regex to extract URLs from the message for individual inspection
    # Captures: 1. Full URL, 2. Domain, 3. Path
    url_regex = r'(https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?)'
    urls = re.findall(url_regex, content, re.IGNORECASE)

    for full_url, domain, path in urls:
        # Normalize domain (lowercase and remove 'www.' for matching)
        clean_domain = domain.lower().replace("www.", "")
        
        if clean_domain in URL_REPLACEMENTS:
            # Get the video path patterns for this specific domain
            patterns = MEDIA_PATTERNS.get(clean_domain, [])
            
            # Check if the URL path matches any of our video/media triggers
            # We use re.search on the path string (e.g., '/reels/XYZ/')
            is_video_link = any(re.search(p, path, re.IGNORECASE) for p in patterns) if path else False
            
            if is_video_link:
                replacement_domain = URL_REPLACEMENTS[clean_domain]
                # Replace the original domain with the fixed one
                fixed_url = full_url.replace(domain, replacement_domain, 1)
                # Update the message content with the fixed URL
                new_content = new_content.replace(full_url, fixed_url)
                found_match = True

    if found_match:
        try:
            # Post the corrected link and credit the original user by nickname
            credit_text = f"Shared by: **{message.author.display_name}**\n{new_content}"
            await message.channel.send(credit_text)
            
            # Delete the original un-embedded link
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
        print(f"CRITICAL: {TOKEN_FILE} not found. Ensure /projects/link-fixer/ is set up.")
