#!/usr/bin/env python3
"""
Lightweight Telegram Video Downloader Bot
Optimized for low-RAM mobile hosting
"""

import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import gc

# ============ CONFIGURATION ============
BOT_TOKEN = "7900353975:AAFqOcr3-q4TnpiVEEuSidWSCrXnnk0I-lI"
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit

# ============ INITIALIZE BOT ============
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Create download directory
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============ YT-DLP BASE OPTIONS ============
def get_yt_opts(quality="best", output_path=None):
    """Return yt-dlp options with Cloudflare bypass headers"""
    opts = {
        # Security & Cloudflare Bypass
        'nocheckcertificate': True,
        'no_warnings': True,
        'quiet': True,
        'no_color': True,
        
        # Browser-like headers
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
        },
        
        # Retry settings
        'retries': 3,
        'fragment_retries': 3,
        
        # Memory optimization
        'buffersize': 1024,
        'noprogress': True,
    }
    
    if output_path:
        opts['outtmpl'] = output_path
        
        # Quality format selection
        if quality == "360p":
            opts['format'] = 'bestvideo[height<=360]+bestaudio/best[height<=360]/worst'
        else:
            opts['format'] = 'bestvideo+bestaudio/best'
    
    return opts


def safe_delete(filepath):
    """Safely delete file and free memory"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"✅ Deleted: {filepath}")
    except Exception as e:
        print(f"⚠️ Delete error: {e}")
    finally:
        gc.collect()  # Force garbage collection


def cleanup_downloads():
    """Clean all files in download directory"""
    try:
        for f in os.listdir(DOWNLOAD_DIR):
            safe_delete(os.path.join(DOWNLOAD_DIR, f))
    except:
        pass


def get_video_info(url):
    """Extract video info without downloading"""
    opts = get_yt_opts()
    opts['skip_download'] = True
    opts['extract_flat'] = False
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'video')[:50],
                'duration': info.get('duration', 0),
                'url': url
            }
    except Exception as e:
        raise e


# ============ USER DATA STORAGE (Minimal) ============
user_links = {}  # {user_id: url}


# ============ BOT HANDLERS ============

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Welcome message"""
    text = """
🎬 <b>Video Downloader Bot</b>

📌 <b>How to use:</b>
1️⃣ Send me any video link
2️⃣ Choose quality (360p or Best)
3️⃣ Wait for download & receive video!

⚠️ <b>Note:</b> Max file size is 50MB

🚀 Send a link to start!
"""
    bot.reply_to(message, text)


@bot.message_handler(func=lambda m: m.text and ('http://' in m.text or 'https://' in m.text))
def handle_link(message):
    """Handle video links"""
    url = message.text.strip()
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Send processing message
    status_msg = bot.send_message(chat_id, "🔍 Checking link...")
    
    try:
        # Extract video info
        info = get_video_info(url)
        
        # Store URL for this user
        user_links[user_id] = url
        
        # Create quality buttons
        keyboard = InlineKeyboardMarkup(row_width=2)
        btn_low = InlineKeyboardButton("📱 Low (360p)", callback_data="quality_360p")
        btn_high = InlineKeyboardButton("🎬 High (Best)", callback_data="quality_best")
        keyboard.add(btn_low, btn_high)
        
        # Update message with video info
        duration_str = ""
        if info['duration']:
            mins, secs = divmod(info['duration'], 60)
            duration_str = f"\n⏱ Duration: {int(mins)}:{int(secs):02d}"
        
        text = f"""
✅ <b>Video Found!</b>

📹 <b>Title:</b> {info['title']}...{duration_str}

👇 <b>Choose quality:</b>
"""
        bot.edit_message_text(text, chat_id, status_msg.message_id, 
                             reply_markup=keyboard, parse_mode="HTML")
        
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        if 'private' in error_str or 'login' in error_str or 'cookie' in error_str:
            bot.edit_message_text(
                "🔒 Site block kar rahi hai, cookies ki zaroorat hai.",
                chat_id, status_msg.message_id
            )
        elif 'expired' in error_str or 'unavailable' in error_str:
            bot.edit_message_text(
                "⏰ Link expired ya unavailable hai.",
                chat_id, status_msg.message_id
            )
        else:
            bot.edit_message_text(
                "❌ Link process nahi ho saka. Check karein link valid hai.",
                chat_id, status_msg.message_id
            )
    except Exception as e:
        bot.edit_message_text(
            "❌ Error occurred. Try again later.",
            chat_id, status_msg.message_id
        )
    finally:
        gc.collect()


@bot.callback_query_handler(func=lambda call: call.data.startswith('quality_'))
def handle_quality_selection(call):
    """Handle quality button clicks"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Get stored URL
    url = user_links.get(user_id)
    if not url:
        bot.answer_callback_query(call.id, "⚠️ Session expired. Send link again.")
        return
    
    # Parse quality
    quality = "360p" if "360p" in call.data else "best"
    quality_text = "360p" if quality == "360p" else "Best"
    
    # Acknowledge button click
    bot.answer_callback_query(call.id, f"⬇️ Downloading {quality_text}...")
    
    # Update message
    bot.edit_message_text(
        f"⬇️ <b>Downloading ({quality_text})...</b>\n\n⏳ Please wait...",
        chat_id, message_id, parse_mode="HTML"
    )
    
    # File path
    output_template = os.path.join(DOWNLOAD_DIR, f"{user_id}_%(title).30s.%(ext)s")
    downloaded_file = None
    
    try:
        # Download video
        opts = get_yt_opts(quality, output_template)
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Get actual filename
            if info.get('requested_downloads'):
                downloaded_file = info['requested_downloads'][0]['filepath']
            else:
                downloaded_file = ydl.prepare_filename(info)
        
        # Check if file exists
        if not downloaded_file or not os.path.exists(downloaded_file):
            raise FileNotFoundError("Download failed")
        
        # Check file size
        file_size = os.path.getsize(downloaded_file)
        if file_size > MAX_FILE_SIZE:
            safe_delete(downloaded_file)
            bot.edit_message_text(
                f"❌ <b>File too large!</b>\n\n"
                f"📦 Size: {file_size // (1024*1024)}MB\n"
                f"📌 Limit: 50MB\n\n"
                f"💡 Try 360p quality for smaller size.",
                chat_id, message_id, parse_mode="HTML"
            )
            return
        
        # Update status
        bot.edit_message_text(
            "📤 <b>Uploading to Telegram...</b>\n\n⏳ Almost done...",
            chat_id, message_id, parse_mode="HTML"
        )
        
        # Send video
        with open(downloaded_file, 'rb') as video_file:
            bot.send_video(
                chat_id,
                video_file,
                caption=f"✅ Downloaded ({quality_text})",
                supports_streaming=True,
                timeout=300
            )
        
        # Success message
        bot.edit_message_text(
            "✅ <b>Done!</b> Video sent successfully.",
            chat_id, message_id, parse_mode="HTML"
        )
        
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        if 'cloudflare' in error_str or 'blocked' in error_str or 'cookie' in error_str:
            bot.edit_message_text(
                "🔒 Site block kar rahi hai, cookies ki zaroorat hai.",
                chat_id, message_id
            )
        elif 'expired' in error_str:
            bot.edit_message_text(
                "⏰ Link expired ho gaya hai.",
                chat_id, message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Download failed. Site ne block kar diya.",
                chat_id, message_id
            )
            
    except Exception as e:
        error_msg = str(e).lower()
        if 'too large' in error_msg or 'file is too big' in error_msg:
            bot.edit_message_text(
                "❌ <b>File too large for Telegram!</b>\n\n"
                "💡 Try 360p quality.",
                chat_id, message_id, parse_mode="HTML"
            )
        else:
            bot.edit_message_text(
                f"❌ Error: Could not process video.",
                chat_id, message_id
            )
    
    finally:
        # ALWAYS delete file to save space
        safe_delete(downloaded_file)
        
        # Clean up user data
        user_links.pop(user_id, None)
        
        # Force garbage collection
        gc.collect()


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    """Handle non-link messages"""
    bot.reply_to(message, "📎 Please send a valid video URL (http:// or https://)")


# ============ MAIN ============
if __name__ == "__main__":
    print("🤖 Bot starting...")
    
    # Clean old downloads on startup
    cleanup_downloads()
    
    # Run bot with auto-reconnect
    while True:
        try:
            print("✅ Bot is running!")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            print("🔄 Restarting in 5 seconds...")
            import time
            time.sleep(5)
            gc.collect()
