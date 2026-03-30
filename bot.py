import discord
import re
import os
import asyncio
import aiohttp
import yt_dlp
from pathlib import Path
from discord.ext import commands, tasks

# --- VERSION TRACKING ---
# v5.5.0 - Restarted from 5.0 base. Added fb.watch & share support. 
# Implemented local download/upload for Facebook content.
VERSION = "5.5.0"

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"
DOWNLOAD_DIR = "/app/downloads"

# Domain mapping for embed-friendly replacements
URL_REPLACEMENTS = {
    "instagram.com": "kkinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "facebook.com": "ezfacebook.com", # Fallback domain
    "tiktok.com": "vxtiktok.com",
    "reddit.com": "vxreddit.com",
}

# Regex patterns for paths that usually indicate a video or media post.
MEDIA_PATTERNS = {
    "instagram.com": [r"/reels?/", r"/p/", r"/tv/"],
    "tiktok.com": [r"/video/", r"/v/", r"/t/"],
    "twitter.com": [r"/status/"],
    "x.com": [r"/status/"],
    "facebook.com": [r"/videos?/", r"/reel/", r"/watch/", r"/share/", r"story\.php"],
    "fb.watch": [r"/"],
    "reddit.com": [r"/comments/", r"/r/.+/s/"], 
    "bsky.app": [r"/post/"],
}

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_fb_video(url):
    """Synchronous function to download FB video via yt-dlp."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][filesize<25M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<25M]/best',
        'outtmpl': f'{DOWNLOAD_DIR}/fb_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

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
    """Updates a file timestamp so Docker healthcheck knows the bot is alive."""
    try:
        Path(HEARTBEAT_FILE).touch()
    except Exception as e:
        print(f"Heartbeat error: {e}")

@bot.event
async def on_ready():
    print("------------------------------------------")
    print(f"LINK FIXER BOT - VERSION {VERSION}")
    print(f"Logged in as: {bot.user.name}")
    print("Status: Active - FB Downloading Enabled")
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

    # Standard URL extraction
    url_regex = r'(https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?)'
    urls = re.findall(url_regex, content, re.IGNORECASE)

    for full_url, domain, path in urls:
        clean_domain = domain.lower().replace("www.", "")
        
        # ADVANCED PROCESSING: v.redd.it
        if clean_domain == "v.redd.it":
            resolved = await resolve_reddit_redirect(full_url)
            if resolved:
                fixed_url = resolved.replace("reddit.com", "vxreddit.com")
                new_content = new_content.replace(full_url, fixed_url)
                found_match = True
            continue

        # NEW: Facebook Download & Upload logic
        if clean_domain in ["facebook.com", "fb.watch"]:
            patterns = MEDIA_PATTERNS.get(clean_domain, [])
            is_fb_video = any(re.search(p, path, re.IGNORECASE) for p in patterns) if path else (clean_domain == "fb.watch")
            
            if is_fb_video:
                try:
                    # Use a thread to prevent blocking the async loop during download
                    file_path = await asyncio.to_thread(download_fb_video, full_url)
                    
                    if os.path.exists(file_path):
                        credit_text = f"Shared by: **{message.author.display_name}**\nSource: <{full_url}>"
                        await message.channel.send(content=credit_text, file=discord.File(file_path))
                        
                        # Cleanup
                        os.remove(file_path)
                        await message.delete()
                        return # Stop processing this message since it's deleted
                except Exception as e:
                    print(f"FB Download failed for {full_url}: {e}")
                    # Fallback to standard rewrite if download fails
                    pass

        # STANDARD CASE: Other platforms
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
