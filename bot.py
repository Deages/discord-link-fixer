import discord
import re
import os
import asyncio
import aiohttp
import yt_dlp
import shutil
import sys
from pathlib import Path
from discord.ext import commands, tasks

# --- VERSION TRACKING ---
# v1.2.2 
# Using vxinstagram.com instead of eeinstagram.com.
VERSION = "1.2.2"

# --- CONFIGURATION ---
TOKEN_FILE = "/app/discordtoken.txt"
HEARTBEAT_FILE = "/app/heartbeat.txt"
DOWNLOAD_DIR = "/app/downloads"
ADMINS_FILE = "/app/admins.txt"
UPDATE_CHANNEL_FILE = "/app/update_channel.txt"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Deages/discord-link-fixer/main/bot.py"

# Domain mapping for embed-friendly replacements
URL_REPLACEMENTS = {
    "instagram.com": "vxinstagram.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "bsky.app": "fxbsky.app",
    "reddit.com": "vxreddit.com",
}

MEDIA_PATTERNS = {
    "instagram.com": [r"/reels?/", r"/p/", r"/tv/"],
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

# Global variables for robustness and monitoring
ADMINS = []
UPDATE_CHANNEL_ID = None
REPORTED_FAILURES = set() # Tracks domains that are currently down to avoid notification spam

def load_config_files():
    """Loads admin IDs and the dedicated update channel ID from local files."""
    global ADMINS, UPDATE_CHANNEL_ID
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r') as f:
            ADMINS = [line.strip() for line in f if line.strip()]
    
    if os.path.exists(UPDATE_CHANNEL_FILE):
        with open(UPDATE_CHANNEL_FILE, 'r') as f:
            content = f.read().strip()
            if content.isdigit():
                UPDATE_CHANNEL_ID = int(content)

async def check_proxy_health(silent=True):
    """
    Checks connectivity for all proxies. 
    If silent=False, it prints to console (used during startup).
    Returns a list of failed domains and their error status.
    """
    results = []
    async with aiohttp.ClientSession() as session:
        for original, replacement in URL_REPLACEMENTS.items():
            try:
                async with session.get(f"https://{replacement}", timeout=8) as resp:
                    # 200 is healthy, 404 is often healthy for proxies with no index page
                    is_online = resp.status in [200, 404]
                    results.append((replacement, is_online, resp.status))
                    if not silent:
                        status_text = "✅ ONLINE" if is_online else "⚠️ UNSTABLE"
                        print(f"{replacement.ljust(18)}: {status_text} (HTTP {resp.status})")
            except Exception as e:
                results.append((replacement, False, str(e)))
                if not silent:
                    print(f"{replacement.ljust(18)}: ❌ OFFLINE")
    return results

async def check_for_updates():
    """Checks GitHub for a newer version string and triggers an update if found."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GITHUB_RAW_URL) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    remote_version = re.search(r'VERSION = "([^"]+)"', text)
                    if remote_version and remote_version.group(1) != VERSION:
                        print(f"Update found: {VERSION} -> {remote_version.group(1)}")
                        sys.exit(0) 
    except Exception as e:
        print(f"Update check failed: {e}")

async def run_startup_validation():
    """Runs system diagnostics and prints results to the terminal."""
    print("\n--- STARTING SYSTEM VALIDATION ---")
    binaries = ["ffmpeg", "yt-dlp", "curl"]
    for binary in binaries:
        path = shutil.which(binary)
        status = "✅ FOUND" if path else "❌ MISSING"
        print(f"Binary {binary.ljust(8)}: {status} ({path or 'N/A'})")

    try:
        test_file = Path(DOWNLOAD_DIR) / "perm_test.txt"
        test_file.touch()
        test_file.unlink()
        print(f"Storage Path    : ✅ READ/WRITE ( {DOWNLOAD_DIR} )")
    except Exception as e:
        print(f"Storage Path    : ❌ PERMISSION ERROR: {e}")

    print("\n--- PROXY SERVICE CONNECTIVITY ---")
    await check_proxy_health(silent=False)
    print("------------------------------------------\n")

@tasks.loop(minutes=10)
async def proxy_monitor_task():
    """Background task to monitor proxy health every 10 minutes and report to Discord."""
    global REPORTED_FAILURES
    if not UPDATE_CHANNEL_ID:
        return

    channel = bot.get_channel(UPDATE_CHANNEL_ID)
    if not channel:
        return

    health_results = await check_proxy_health(silent=True)
    
    for domain, is_online, status in health_results:
        if not is_online:
            if domain not in REPORTED_FAILURES:
                # New failure detected
                error_msg = f"❌ **Service Alert: {domain}**\nStatus: `Offline/Unstable` (HTTP {status})\nEmbeds for this platform may fail."
                await channel.send(error_msg)
                REPORTED_FAILURES.add(domain)
        else:
            if domain in REPORTED_FAILURES:
                # Service has recovered
                recovery_msg = f"✅ **Service Restored: {domain}**\nStatus: `Online` (HTTP {status})"
                await channel.send(recovery_msg)
                REPORTED_FAILURES.remove(domain)

@tasks.loop(minutes=15)
async def auto_update_task():
    """Background task to periodically check for updates."""
    await check_for_updates()

@tasks.loop(seconds=30)
async def update_heartbeat():
    """Updates a file timestamp for Docker healthchecks."""
    try:
        Path(HEARTBEAT_FILE).touch()
    except Exception as e:
        print(f"Heartbeat error: {e}")

@bot.event
async def on_ready():
    load_config_files()
    print("------------------------------------------")
    print(f"LINK FIXER BOT - VERSION {VERSION}")
    print(f"Logged in as: {bot.user.name}")
    print(f"Admins Loaded: {len(ADMINS)}")
    print("------------------------------------------")
    
    await run_startup_validation()
    
    if not update_heartbeat.is_running():
        update_heartbeat.start()
    if not auto_update_task.is_running():
        auto_update_task.start()
    if not proxy_monitor_task.is_running():
        proxy_monitor_task.start()

    if UPDATE_CHANNEL_ID:
        channel = bot.get_channel(UPDATE_CHANNEL_ID)
        if channel:
            await channel.send(f"✅ **Link Fixer Online** (v{VERSION})\nDiagnostics complete. Proxy monitoring active (10m interval).")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith("!update") and str(message.author.id) in ADMINS:
        await message.channel.send("🔄 Manual update triggered. Checking GitHub...")
        await check_for_updates()
        return

    content = message.content
    new_content = content
    found_match = False

    url_regex = r'(https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?)'
    urls = re.findall(url_regex, content, re.IGNORECASE)

    for full_url, domain, path in urls:
        clean_domain = domain.lower().replace("www.", "")
        
        # Reddit Redirect
        if clean_domain == "v.redd.it":
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(full_url, allow_redirects=True, timeout=5) as resp:
                        resolved = str(resp.url)
                        if "reddit.com/r/" in resolved:
                            fixed_url = resolved.replace("reddit.com", "vxreddit.com")
                            new_content = new_content.replace(full_url, fixed_url)
                            found_match = True
            except: pass
            continue

        # Facebook Local Processing
        if any(x in clean_domain for x in ["facebook.com", "fb.watch"]):
            patterns = MEDIA_PATTERNS.get(clean_domain, [])
            is_fb_video = any(re.search(p, path, re.IGNORECASE) for p in patterns) if path else (clean_domain == "fb.watch")
            if is_fb_video:
                try:
                    file_path = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL({
                        'format': 'bestvideo[ext=mp4][filesize<25M]+bestaudio[ext=m4a]/best',
                        'outtmpl': f'{DOWNLOAD_DIR}/fb_%(id)s.%(ext)s',
                        'quiet': True,
                    }).prepare_filename(yt_dlp.YoutubeDL({'quiet': True}).extract_info(full_url, download=True)))
                    
                    if os.path.exists(file_path):
                        await message.channel.send(content=f"Shared by: **{message.author.display_name}**\nSource: <{full_url}>", file=discord.File(file_path))
                        os.remove(file_path)
                        await message.delete()
                        return 
                except: pass

        # Standard Domain Rewrites
        if clean_domain in URL_REPLACEMENTS:
            patterns = MEDIA_PATTERNS.get(clean_domain, [])
            if any(re.search(p, path, re.IGNORECASE) for p in patterns) if path else False:
                replacement_domain = URL_REPLACEMENTS[clean_domain]
                fixed_url = full_url.replace(domain, replacement_domain, 1)
                
                if clean_domain == "instagram.com":
                    fixed_url = fixed_url.split('?')[0]
                
                new_content = new_content.replace(full_url, fixed_url)
                found_match = True

    if found_match:
        try:
            await message.channel.send(f"Shared by: **{message.author.display_name}**\n{new_content}")
            await message.delete()
        except Exception as e:
            print(f"Error handling message: {e}")

if __name__ == "__main__":
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token = f.read().strip()
        bot.run(token)
    else:
        print("CRITICAL: TOKEN_FILE not found.")
