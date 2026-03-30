# Discord Embed Link Fixer 

A robust, self-healing Discord bot designed to "fix" social media links so they embed correctly in text channels. This bot is specifically optimized for **Home Lab** environments using **Docker** and **Dockge**, providing local video processing for platforms with aggressive embed blocks.

## 🚀 Overview

Tired of links that don't show a video preview? This bot monitors your Discord server for social media links (Instagram, X/Twitter, Reddit, etc.) and automatically:
1.  **Rewrites** them to use community-maintained "embed-fixer" domains.
2.  **Resolves** shortened or direct media links (like `v.redd.it`) to their full post context.
3.  **Downloads & Uploads** Facebook Reels/Videos locally to bypass Meta's embed restrictions.
4.  **Credits** the original poster using their server nickname (without annoying pings).
5.  **Cleans up** by deleting the original "broken" link.

---

## ✨ Features

* **Local Video Processing:** Uses `yt-dlp` and `ffmpeg` to download Facebook videos locally and re-upload them to Discord, ensuring the video actually plays.
* **Startup Validation Suite:** On boot, the bot runs a diagnostic check on all required binaries (`ffmpeg`, `yt-dlp`), folder permissions, and the connectivity status of all proxy domains.
* **Reddit Redirect Resolver:** Automatically follows `v.redd.it` redirects to find the original post and feed it into `vxreddit`.
* **Home Lab Ready:** Includes a heartbeat system compatible with Docker Healthchecks to ensure 24/7 uptime.
* **Privacy Minded:** Credits users by bolding their nickname rather than tagging/pinging them.

---

## 📱 Supported Platforms

| Platform | Fix Method | Proxy Used |
| :--- | :--- | :--- |
| **Instagram** | Rewrite | `kkinstagram.com` |
| **Twitter / X** | Rewrite | `fxtwitter.com` / `fixupx.com` |
| **Reddit** | Redirect + Rewrite | `vxreddit.com` |
| **Bluesky** | Rewrite | `fxbsky.app` |
| **Facebook / fb.watch** | **Local Download** | Native MP4 Upload |

*Note: TikTok processing is currently disabled as native Discord embeds are functional.*

---

## 🛠️ Setup Instructions

### 1. Discord Developer Portal
1.  Create a new application at the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Under the **Bot** tab, enable the **Message Content Intent**.
3.  Reset/Copy your **Bot Token**.
4.  Use the **OAuth2 URL Generator** to invite the bot to your server with `Manage Messages`, `Send Messages`, `Attach Files`, and `Read Message History` permissions.

### 2. Local Environment (Host Machine)
The bot expects a specific folder structure on your host (optimized for Linux/Debian).
```bash
mkdir -p /projects/link-fixer
# Create the token file and paste your token inside
echo "YOUR_DISCORD_BOT_TOKEN" > /projects/link-fixer/discordtoken.txt
```

### 3. Docker Deployment (Dockge/Compose)
This repository includes a `compose.yaml` designed for **Dockge**. It handles all dependencies (`ffmpeg`, `yt-dlp`) and pulls the latest `bot.py` directly from this repo on startup.

1.  Open your **Dockge** GUI.
2.  Create a new stack named `link-fixer`.
3.  Paste the contents of the `compose.yaml` found in this repository.
4.  Deploy the stack.

---

## 🩺 Health & Troubleshooting
Check the **Dockge Terminal** during startup to see the validation report.

* **Binary Checks:** Ensure `ffmpeg` and `yt-dlp` show as `✅ FOUND`.
* **Proxy Status:** If a proxy domain shows as `❌ OFFLINE`, the bot will still attempt to rewrite links, but embeds may fail until that third-party service is restored.
* **Permissions:** Ensure the `/app/downloads` path is `✅ READ/WRITE`.
