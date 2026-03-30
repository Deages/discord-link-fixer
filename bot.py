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
    "reddit.com": "vxreddit.com",  # Using vxreddit as requested for better v.redd.it compatibility
}

# Regex patterns for paths that usually indicate a video or media post.
MEDIA_PATTERNS = {
    "instagram.com": [r"/reels?/", r"/p/", r"/tv/"],
    "tiktok.com": [r"/video/", r"/v/", r"/t/"],
    "twitter.com": [r"/status/"],
    "x.com": [r"/status/"],
    "facebook.com": [r"/videos?/", r"/reel/", r"/watch/", r"story\.php"],
    "reddit.com": [r"/comments/", r"/r/.+/s/"], # Support for standard and short-share links
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
    print("Link Fixer active: v.redd.it reformatting enabled.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content
    new_content = content
    found_match = False

    # Standard URL extraction
    url_regex = r'(https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?)'
    urls = re.findall(url_regex, content, re.IGNORECASE)

    for full_url, domain, path in urls:
        clean_domain = domain.lower().replace("www.", "")
        
        # SPECIAL CASE: v.redd.it (Direct video URLs)
        # These need to be converted to a post format for vxreddit to work.
        if clean_domain == "v.redd.it":
            video_id = path.strip("/")
            # Convert https://v.redd.it/ID to https://vxreddit.com/ID
            # vxreddit handles the 'v.redd.it' ID as a direct path if 'www' is omitted
            fixed_url = f"https://vxreddit.com/{video_id}"
            new_content = new_content.replace(full_url, fixed_url)
            found_match = True
            continue

        # STANDARD CASE: Domain Replacement
        if clean_domain in URL_REPLACEMENTS:
            patterns = MEDIA_PATTERNS.get(clean_domain, [])
            is_video_link = any(re.search(p, path, re.IGNORECASE) for p in patterns) if path else False
            
            if is_video_link:
                replacement_domain = URL_REPLACEMENTS[clean_domain]
                fixed_url = full_url.replace(domain, replacement_domain, 1)
                new_content = new_content.replace(full_url, fixed_url)
                found_match = True

    if found_match:
        try:
            credit_text = f"Shared by: **{message.author.display_name}**\n{new_content}"
            await message.channel.send(credit_text)
            await message.delete()
        except Exception as e:
            print(f"Error handling message: {e}")

if __name__ == "__main__":
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token = f.read().strip()
        bot.run(token)
    else:
        print(f"CRITICAL: {TOKEN_FILE} not found.")
