import discord
import re
import os
import asyncio
import aiohttp
from pathlib import Path
from discord.ext import commands, tasks

# --- VERSION TRACKING ---
VERSION = "5.3.0"

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"

# Domain mapping for embed-friendly replacements
URL_REPLACEMENTS = {
    "instagram.com": "kkinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "facebook.com": "ezfacebook.com", # Swapped to ezfacebook for better Reel support
    "fb.watch": "ezfacebook.com",     # Supporting the shortener
    "tiktok.com": "vxtiktok.com",
    "reddit.com": "vxreddit.com",
}

# Regex patterns for paths that usually indicate a video or media post.
MEDIA_PATTERNS = {
    "instagram.com": [r"/reels?/", r"/p/", r"/tv/"],
    "tiktok.com": [r"/video/", r"/v/", r"/t/"],
    "twitter.com": [r"/status/"],
    "x.com": [r"/status/"],
    "facebook.com": [r"/videos?/", r"/reel/", r"/watch/", r"story\.php"],
    "fb.watch": [r"/"], 
    "reddit.com": [r"/comments/", r"/r/.+/s/"], 
    "bsky.app": [r"/post/"],
}

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

async def resolve_reddit_redirect(url):
    """Follows v.redd.it redirects to find the full Reddit post URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=5) as response:
                resolved_url = str(response.url)
                if "reddit.com/r/" in resolved_url:
                    return resolved_url
    except Exception as e:
        print(f"Error resolving redirect for {url}: {e}")
    return None

@tasks.loop(seconds=30)
async def update_heartbeat():
    try:
        Path(HEARTBEAT_FILE).touch()
    except Exception as e:
        print(f"Heartbeat error: {e}")

@bot.event
async def on_ready():
    print("------------------------------------------")
    print(f"LINK FIXER BOT - VERSION {VERSION}")
    print(f"Logged in as: {bot.user.name}")
    print("Status: Active (EZFacebook + Reddit Fix)")
    print("------------------------------------------")
    if not update_heartbeat.is_running():
        update_heartbeat.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content
    new_content = content
    found_match = False

    url_regex = r'(https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?)'
    urls = re.findall(url_regex, content, re.IGNORECASE)

    for full_url, domain, path in urls:
        clean_domain = domain.lower().replace("www.", "")
        
        # Reddit Redirect Handling
        if clean_domain == "v.redd.it":
            resolved = await resolve_reddit_redirect(full_url)
            if resolved:
                fixed_url = resolved.replace("reddit.com", "vxreddit.com")
                new_content = new_content.replace(full_url, fixed_url)
                found_match = True
            continue

        # General Domain Replacement
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
