#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Video Downloader Bot
Auto-installs dependencies and downloads videos from lecture websites
"""

# ============================================
# AUTO-INSTALL DEPENDENCIES
# ============================================
import subprocess
import sys

def install_packages():
    """Automatically install required packages if not present"""
    packages = ['pyTelegramBotAPI', 'yt-dlp']
    for package in packages:
        try:
            if package == 'pyTelegramBotAPI':
                __import__('telebot')
            else:
                __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '--quiet'])

# Run installation check
install_packages()

# ============================================
# IMPORTS (after installation)
# ============================================
import os
import telebot
from telebot import types
import yt_dlp
import threading
import time
import re

# ============================================
# BOT CONFIGURATION
# ============================================
BOT_TOKEN = "7900353975:AAFqOcr3-q4TnpiVEEuSidWSCrXnnk0I-lI"
bot = telebot.TeleBot(BOT_TOKEN)

# Store user URLs temporarily
user_data = {}

# ============================================
# YT-DLP CONFIGURATION WITH CLOUDFLARE BYPASS
# ============================================
YDL_BASE_OPTIONS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 3,
    'nocheckcertificate': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    },
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def is_valid_url(url):
    """Check if the provided string is a valid URL"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def get_video_info(url):
    """Extract video information using yt-dlp"""
    ydl_opts = YDL_BASE_OPTIONS.copy()
    ydl_opts['skip_download'] = True
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

def download_video(url, quality='best', chat_id=None):
    """Download video with specified quality"""
    timestamp = int(time.time())
    filename = f"video_{chat_id}_{timestamp}"
    
    ydl_opts = YDL_BASE_OPTIONS.copy()
    ydl_opts['outtmpl'] = f'{filename}.%(ext)s'
    
    if quality == 'low':
        # 360p or closest low quality
        ydl_opts['format'] = 'bestvideo[height<=360]+bestaudio/best[height<=360]/worst'
    else:
        # Best quality available
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    
    # Merge to mp4 if possible
    ydl_opts['merge_output_format'] = 'mp4'
    ydl_opts['postprocessors'] = [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }]
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Get the actual downloaded filename
        if 'requested_downloads' in info:
            downloaded_file = info['requested_downloads'][0]['filepath']
        else:
            # Fallback to finding the file
            ext = info.get('ext', 'mp4')
            downloaded_file = f"{filename}.{ext}"
        
        return downloaded_file, info.get('title', 'Video')

def delete_file_safely(filepath):
    """Delete file from server to save space"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"Deleted: {filepath}")
    except Exception as e:
        print(f"Error deleting file: {e}")

def find_and_delete_files(pattern):
    """Find and delete files matching a pattern"""
    import glob
    for filepath in glob.glob(pattern):
        delete_file_safely(filepath)

# ============================================
# BOT HANDLERS
# ============================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handle /start and /help commands"""
    welcome_text = """
🎬 *Video Downloader Bot*

📌 *How to use:*
1️⃣ Send me a video URL (lecture link)
2️⃣ Choose quality (Low 360p or High Best)
3️⃣ Wait for download & receive your video!

📝 *Commands:*
/start - Show this message
/help - Show help

⚡ Just send any video URL to get started!
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_url(message):
    """Handle URL messages from users"""
    url = message.text.strip()
    chat_id = message.chat.id
    
    # Validate URL
    if not is_valid_url(url):
        bot.reply_to(message, "❌ Please send a valid URL!\n\nExample: https://example.com/lecture/video")
        return
    
    # Send processing message
    processing_msg = bot.reply_to(message, "🔍 Checking video link... Please wait...")
    
    try:
        # Try to extract video info
        info = get_video_info(url)
        
        if not info:
            bot.edit_message_text(
                "❌ Could not find any video at this URL.",
                chat_id=chat_id,
                message_id=processing_msg.message_id
            )
            return
        
        # Store URL for this user
        user_data[chat_id] = {
            'url': url,
            'title': info.get('title', 'Video')
        }
        
        # Get video title and duration
        title = info.get('title', 'Unknown')[:50]
        duration = info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
        
        # Create inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_low = types.InlineKeyboardButton("📉 Low Quality (360p)", callback_data="quality_low")
        btn_high = types.InlineKeyboardButton("📈 High Quality (Best)", callback_data="quality_high")
        markup.add(btn_low, btn_high)
        
        # Send quality selection
        bot.edit_message_text(
            f"✅ *Video Found!*\n\n"
            f"📌 *Title:* {title}\n"
            f"⏱ *Duration:* {duration_str}\n\n"
            f"👇 Select video quality:",
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        if 'cloudflare' in error_str or '403' in error_str or 'blocked' in error_str or 'expired' in error_str:
            bot.edit_message_text(
                "🚫 Site block kar rahi hai, cookies ki zaroorat hai.",
                chat_id=chat_id,
                message_id=processing_msg.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Error: Could not extract video.\n\nSite block kar rahi hai, cookies ki zaroorat hai.",
                chat_id=chat_id,
                message_id=processing_msg.message_id
            )
    except Exception as e:
        bot.edit_message_text(
            "🚫 Site block kar rahi hai, cookies ki zaroorat hai.",
            chat_id=chat_id,
            message_id=processing_msg.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('quality_'))
def handle_quality_selection(call):
    """Handle quality button clicks"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Get stored URL
    if chat_id not in user_data:
        bot.answer_callback_query(call.id, "❌ Session expired! Please send the URL again.")
        return
    
    url = user_data[chat_id]['url']
    title = user_data[chat_id]['title']
    
    # Determine quality
    quality = 'low' if call.data == 'quality_low' else 'best'
    quality_text = "360p (Low)" if quality == 'low' else "Best (High)"
    
    # Acknowledge button click
    bot.answer_callback_query(call.id, f"Downloading {quality_text}...")
    
    # Update message
    bot.edit_message_text(
        f"⬇️ *Downloading...*\n\n"
        f"📌 Quality: {quality_text}\n"
        f"⏳ Please wait, this may take a few minutes...",
        chat_id=chat_id,
        message_id=message_id,
        parse_mode='Markdown'
    )
    
    # Download in thread to avoid blocking
    def download_and_send():
        filepath = None
        try:
            # Download video
            filepath, video_title = download_video(url, quality, chat_id)
            
            if not os.path.exists(filepath):
                bot.send_message(chat_id, "❌ Download failed. File not found.")
                return
            
            # Check file size (Telegram limit is 50MB for bots)
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 50:
                bot.send_message(
                    chat_id,
                    f"⚠️ Video is too large ({file_size_mb:.1f}MB).\n"
                    f"Telegram limit is 50MB.\n"
                    f"Try downloading Low Quality (360p) instead."
                )
                delete_file_safely(filepath)
                return
            
            # Send uploading status
            bot.edit_message_text(
                f"📤 *Uploading to Telegram...*\n\n"
                f"📦 Size: {file_size_mb:.1f} MB",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='Markdown'
            )
            
            # Send video file
            with open(filepath, 'rb') as video_file:
                bot.send_video(
                    chat_id,
                    video_file,
                    caption=f"✅ {video_title[:100]}\n\n📊 Quality: {quality_text}\n📦 Size: {file_size_mb:.1f} MB",
                    supports_streaming=True,
                    timeout=300
                )
            
            # Update final message
            bot.edit_message_text(
                f"✅ *Download Complete!*\n\n"
                f"📌 {video_title[:50]}",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='Markdown'
            )
            
        except yt_dlp.utils.DownloadError as e:
            bot.edit_message_text(
                "🚫 Site block kar rahi hai, cookies ki zaroorat hai.",
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            error_msg = str(e).lower()
            if 'cloudflare' in error_msg or '403' in error_msg or 'blocked' in error_msg:
                bot.edit_message_text(
                    "🚫 Site block kar rahi hai, cookies ki zaroorat hai.",
                    chat_id=chat_id,
                    message_id=message_id
                )
            else:
                bot.edit_message_text(
                    f"❌ Download failed!\n\nSite block kar rahi hai, cookies ki zaroorat hai.",
                    chat_id=chat_id,
                    message_id=message_id
                )
        finally:
            # ALWAYS delete the file to save space
            if filepath:
                delete_file_safely(filepath)
            
            # Also clean up any partial downloads
            find_and_delete_files(f"video_{chat_id}_*")
            
            # Clear user data
            if chat_id in user_data:
                del user_data[chat_id]
    
    # Start download thread
    thread = threading.Thread(target=download_and_send)
    thread.start()

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Telegram Video Downloader Bot Starting...")
    print("=" * 50)
    print("Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    
    # Clean up any leftover files from previous sessions
    find_and_delete_files("video_*")
    
    # Start polling with error handling
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot error: {e}")
            print("Restarting in 5 seconds...")
            time.sleep(5)
