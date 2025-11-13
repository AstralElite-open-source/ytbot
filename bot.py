import os
import asyncio
import math
import subprocess
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.request import HTTPXRequest
import yt_dlp
import re
import aiohttp

# Bot token from environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required!")

# Telegram Bot API URL (use local server if available, otherwise standard API)
TELEGRAM_BOT_API_URL = os.getenv('TELEGRAM_BOT_API_URL', 'https://api.telegram.org')

# Telegram file size limit
# 50MB for standard API, 2GB for self-hosted local Bot API
if 'localhost' in TELEGRAM_BOT_API_URL or '127.0.0.1' in TELEGRAM_BOT_API_URL or 'telegram-bot-api' in TELEGRAM_BOT_API_URL:
    TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024  # 2 GB (self-hosted)
    print("🚀 Using self-hosted Bot API - 2GB file limit")
else:
    TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024  # 50 MB (standard API)
    print("⚠️ Using standard Bot API - 50MB file limit")

# Store video info temporarily
user_data = {}

# Track active downloads per user (for concurrent support)
active_downloads = {}

def is_youtube_url(url):
    """Check if the URL is a valid YouTube URL (including playlists and channels)"""
    patterns = [
        r'(https?://)?(www\.|m\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})',
        r'(https?://)?(www\.|m\.)?(youtube|youtu)\.(com)/playlist\?list=',
        r'(https?://)?(www\.|m\.)?(youtube)\.(com)/(c/|channel/|user/|@)',
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def is_playlist_or_channel(url):
    """Check if URL is a playlist or channel"""
    return 'playlist?list=' in url or '/channel/' in url or '/c/' in url or '/user/' in url or '/@' in url

def format_bytes(bytes_num):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def create_progress_bar(percent):
    """Create a visual progress bar for uploads"""
    filled = int(percent / 10)
    empty = 10 - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percent:.1f}%"

def split_file_by_parts(input_path, max_bytes=TELEGRAM_FILE_LIMIT):
    """Split large files into parts using ffmpeg"""
    size = os.path.getsize(input_path)
    if size <= max_bytes:
        return [input_path]
    
    print(f"File {input_path} is {size} bytes, splitting into parts...")
    
    # Get duration using ffprobe
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_path
    ]
    try:
        duration_output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        duration = float(duration_output)
    except Exception as e:
        print(f"Could not get duration: {e}")
        duration = None
    
    if duration:
        # Calculate number of parts needed
        parts = math.ceil(size / max_bytes)
        segment_time = math.ceil(duration / parts)
        
        # Split using ffmpeg
        out_pattern = input_path + '_part_%03d.mp4'
        split_cmd = [
            'ffmpeg', '-i', input_path, '-c', 'copy',
            '-map', '0', '-f', 'segment', '-segment_time', str(segment_time),
            '-reset_timestamps', '1', out_pattern, '-y'
        ]
        print(f"Splitting into {parts} parts of ~{segment_time}s each...")
        subprocess.check_call(split_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        parts_files = sorted(glob.glob(input_path + '_part_*.mp4'))
        print(f"Split into {len(parts_files)} parts")
        return parts_files
    else:
        # Can't split without duration, return original
        return [input_path]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Welcome to YouTube Downloader Bot!\n\n"
        "📺 Simply send me a YouTube link and I'll help you download it.\n\n"
        "Usage: Just paste any YouTube video URL"
    )

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sticker messages and print their file_id"""
    sticker = update.message.sticker
    await update.message.reply_text(
        f"📌 Sticker File ID:\n`{sticker.file_id}`\n\n"
        f"Copy this ID to use in the bot!",
        parse_mode='Markdown'
    )
    print(f"Sticker file_id: {sticker.file_id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages (YouTube links)"""
    message = update.message.text
    user_id = update.message.from_user.id
    
    if is_youtube_url(message):
        # Delete user's URL message for cleaner chat
        try:
            await update.message.delete()
        except:
            pass
        
        fetching_msg = await context.bot.send_message(
            chat_id=user_id,
            text="🔍 Fetching video information..."
        )
        
        try:
            # Get video info
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(message, download=False)
                
                # Check if it's a playlist or channel
                is_playlist = is_playlist_or_channel(message) or info.get('_type') == 'playlist'
                
                if is_playlist:
                    # Handle playlist/channel
                    entries = info.get('entries', [])
                    video_count = len(entries)
                    
                    user_data[user_id] = {
                        'url': message,
                        'title': info.get('title', 'Unknown'),
                        'is_playlist': True,
                        'video_count': video_count
                    }
                    
                    keyboard = [
                        [InlineKeyboardButton("🎥 Download All (720p)", callback_data='playlist_720p')],
                        [InlineKeyboardButton("📹 Download All (480p)", callback_data='playlist_480p')],
                        [InlineKeyboardButton("🎵 Download All (Audio Only)", callback_data='playlist_audio')],
                        [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Delete fetching message
                    try:
                        await fetching_msg.delete()
                    except:
                        pass
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📑 Playlist/Channel found!\n\n"
                        f"📝 Title: {info.get('title', 'Unknown')}\n"
                        f"📊 Videos: {video_count}\n\n"
                        f"⚠️ Note: Large playlists may take time!\n\n"
                        f"Please select quality:",
                        reply_markup=reply_markup
                    )
                else:
                    # Handle single video
                    user_data[user_id] = {
                        'url': message,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'is_playlist': False
                    }
                    
                    duration = info.get('duration', 0)
                
                # Get available formats and build quality options dynamically
                formats = info.get('formats', [])
                available_qualities = set()
                
                for f in formats:
                    height = f.get('height')
                    if height is None:
                        continue
                    if height >= 1080:
                        available_qualities.add('1080p')
                    elif height >= 720:
                        available_qualities.add('720p')
                    elif height >= 480:
                        available_qualities.add('480p')
                    elif height >= 360:
                        available_qualities.add('360p')
                
                # Build quality buttons based on available formats
                keyboard = []
                
                if '1080p' in available_qualities:
                    keyboard.append([InlineKeyboardButton("� Full HD (1080p)", callback_data='quality_1080p')])
                if '720p' in available_qualities:
                    keyboard.append([InlineKeyboardButton("🎥 HD (720p)", callback_data='quality_720p')])
                if '480p' in available_qualities:
                    keyboard.append([InlineKeyboardButton("📹 SD (480p)", callback_data='quality_480p')])
                if '360p' in available_qualities:
                    keyboard.append([InlineKeyboardButton("📱 Low (360p)", callback_data='quality_360p')])
                
                # Always add audio option
                keyboard.append([InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='quality_audio')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
                
                qualities_text = ", ".join(sorted(available_qualities, key=lambda x: int(x[:-1]), reverse=True))
                
                # Delete fetching message
                try:
                    await fetching_msg.delete()
                except:
                    pass
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Video found!\n\n"
                    f"📝 Title: {info.get('title', 'Unknown')}\n"
                    f"⏱️ Duration: {duration_str}\n"
                    f"🎬 Available: {qualities_text}\n\n"
                    f"Please select quality:",
                    reply_markup=reply_markup
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}\n\nPlease make sure the link is valid.")
    else:
        await update.message.reply_text(
            "⚠️ Please send a valid YouTube URL.\n\n"
            "Example: https://www.youtube.com/watch?v=..."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks for quality selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.answer("Session expired!")
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return
    
    await query.answer()
    
    video_url = user_data[user_id]['url']
    video_title = user_data[user_id]['title']
    
    # Determine quality settings
    quality_map = {
        'quality_1080p': {'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'label': '1080p'},
        'quality_720p': {'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'label': '720p'},
        'quality_480p': {'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'label': '480p'},
        'quality_360p': {'format': 'bestvideo[height<=360]+bestaudio/best[height<=360]', 'label': '360p'},
        'quality_audio': {'format': 'bestaudio/best', 'label': 'MP3'},
        'playlist_720p': {'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'label': '720p'},
        'playlist_480p': {'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'label': '480p'},
        'playlist_audio': {'format': 'bestaudio/best', 'label': 'MP3'}
    }
    
    selected_quality = quality_map.get(query.data)
    
    if not selected_quality:
        if query.data == 'cancel':
            await query.edit_message_text("❌ Download cancelled")
            if user_id in user_data:
                del user_data[user_id]
            return
        await query.edit_message_text("❌ Invalid selection.")
        return
    
    # Check if it's a playlist download
    is_playlist_download = query.data.startswith('playlist_')
    video_info = user_data[user_id]
    
    # Mark user as having active download
    active_downloads[user_id] = True
    
    # Delete quality selection message for cleaner chat
    try:
        await query.message.delete()
    except:
        pass
    
    if is_playlist_download:
        downloading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"📥 Downloading playlist in {selected_quality['label']}...\n\n"
            f"📊 Videos: {video_info.get('video_count', '?')}\n"
            f"⏳ This may take a while...\n\n"
            f"💡 Videos will be sent one by one as they complete!"
        )
        sticker_message = None
    else:
        # Send animated downloading sticker for single videos
        downloading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"⬇️ Downloading {selected_quality['label']}..."
        )
        sticker_message = await context.bot.send_sticker(
            chat_id=user_id,
            sticker="CAACAgIAAxkBAAIBHWkVql0BTU95XYHcF7T0pX3X-ggJAAJLAgACVp29CmJQRdBQ-nGcNgQ"
        )
    
    try:
        # Download settings
        output_path = 'downloads'
        os.makedirs(output_path, exist_ok=True)
        
        ydl_opts = {
            'format': selected_quality['format'],
            'outtmpl': f"{output_path}/%(title)s.%(ext)s",
            'quiet': True,
            'no_warnings': True,
        }
        
        # Add audio conversion for MP3
        if query.data == 'quality_audio' or query.data == 'playlist_audio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]
        else:
            ydl_opts['merge_output_format'] = 'mp4'
        
        # Download the video/playlist
        download_complete = False
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            download_complete = True
            
            # Delete downloading message and sticker for single video
            if not is_playlist_download:
                try:
                    await downloading_msg.delete()
                except:
                    pass
                if sticker_message:
                    try:
                        await sticker_message.delete()
                    except:
                        pass
            
            # Handle playlist downloads
            if is_playlist_download:
                entries = info.get('entries', [])
                successful_uploads = 0
                failed_uploads = 0
                
                # Update message after all downloads complete
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ All {len(entries)} files downloaded!\n📤 Starting uploads..."
                )
                
                for idx, entry in enumerate(entries):
                    try:
                        # Get the downloaded file path for this entry
                        if query.data == 'playlist_audio':
                            entry_filename = ydl.prepare_filename(entry).rsplit('.', 1)[0] + '.mp3'
                        else:
                            entry_filename = ydl.prepare_filename(entry)
                        
                        if not os.path.exists(entry_filename):
                            failed_uploads += 1
                            continue
                        
                        entry_file_size = os.path.getsize(entry_filename)
                        
                        # Send progress update with counter
                        progress_msg = await context.bot.send_message(
                            chat_id=user_id,
                            text=f"📤 Uploading {idx + 1}/{len(entries)}\n"
                                 f"📝 {entry.get('title', 'Unknown')[:50]}..."
                        )
                        
                        # Upload the file
                        entry_duration = int(entry.get('duration') or 0)
                        entry_title = entry.get('title', 'Unknown')
                        
                        if query.data == 'playlist_audio':
                            await context.bot.send_audio(
                                chat_id=user_id,
                                audio=open(entry_filename, 'rb'),
                                title=entry_title,
                                performer=entry.get('uploader', 'YouTube'),
                                duration=entry_duration,
                                read_timeout=600,
                                write_timeout=600,
                                connect_timeout=30,
                                pool_timeout=30
                            )
                        else:
                            await context.bot.send_video(
                                chat_id=user_id,
                                video=open(entry_filename, 'rb'),
                                duration=entry_duration,
                                caption=entry_title[:1024],
                                supports_streaming=True,
                                read_timeout=600,
                                write_timeout=600,
                                connect_timeout=30,
                                pool_timeout=30
                            )
                        
                        successful_uploads += 1
                        
                        # Clean up the file
                        try:
                            os.remove(entry_filename)
                        except:
                            pass
                    
                    except Exception as e:
                        failed_uploads += 1
                        print(f"Error uploading video {idx + 1}: {str(e)}")
                
                # Send summary
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ download complete!\n\n"
                         f"📊 Total videos: {len(entries)}\n"
                         f"✅ Successful: {successful_uploads}\n"
                         f"❌ Failed: {failed_uploads}"
                )
                
                # Cleanup
                if user_id in user_data:
                    del user_data[user_id]
                if user_id in active_downloads:
                    del active_downloads[user_id]
                
                return
            
            # Get the downloaded file path (single video)
            if query.data == 'quality_audio':
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
        
        # Verify file exists
        if not os.path.exists(filename):
            print(f"ERROR: File not found: {filename}")
            await query.message.reply_text("❌ Error: Downloaded file not found!")
            if user_id in active_downloads:
                del active_downloads[user_id]
            if user_id in user_data:
                del user_data[user_id]
            return
        
        print(f"File exists: {filename}, size: {os.path.getsize(filename)} bytes")
        
        # Mark as complete
        # Get file size for upload info
        file_size = os.path.getsize(filename)
        print(f"Starting upload for user {user_id}, file: {filename}, size: {file_size}")
        
        # Track upload progress with animation
        upload_message = await context.bot.send_message(
            chat_id=user_id,
            text=f"📤 Uploading...\n\n"
            f"💾 Size: {format_bytes(file_size)}\n"
            f"⏳ Starting..."
        )
        
        # Start upload progress estimator
        async def upload_progress():
            start_time = asyncio.get_event_loop().time()
            # Estimate upload time based on file size (assume ~5MB/s average)
            estimated_duration = file_size / (5 * 1024 * 1024)  # seconds
            
            while True:
                try:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    progress_percent = min(95, (elapsed / estimated_duration) * 100) if estimated_duration > 0 else 0
                    
                    filled = int(progress_percent / 10)
                    empty = 10 - filled
                    bar = "█" * filled + "░" * empty
                    
                    await upload_message.edit_text(
                        f"📤 Uploading...\n\n"
                        f"[{bar}] {progress_percent:.1f}%\n\n"
                        f"💾 Size: {format_bytes(file_size)}\n"
                        f"⏱️ Time: {int(elapsed)}s"
                    )
                    await asyncio.sleep(1)
                except:
                    break
        
        animation_task = asyncio.create_task(upload_progress())
        
        try:
            # Send the file directly
            print(f"Attempting to upload file: {filename}")
            print(f"File size: {format_bytes(file_size)}")
            
            # Upload directly - no splitting needed with 2GB limit
            print(f"Uploading...")
            
            if query.data == 'quality_audio':
                print("Uploading as audio...")
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=open(filename, 'rb'),
                    title=video_title,
                    read_timeout=600,
                    write_timeout=600
                )
                print("Audio upload successful!")
            else:
                print("Uploading as video...")
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=open(filename, 'rb'),
                    caption=f"📹 {video_title}",
                    supports_streaming=True,
                    read_timeout=600,
                    write_timeout=600
                )
                print("Video upload successful!")
        except Exception as upload_error:
            print(f"Upload error: {type(upload_error).__name__}: {upload_error}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Stop animation
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass
        
        # Clean up
        os.remove(filename)
        # Delete upload progress message for cleaner chat
        try:
            await upload_message.delete()
        except:
            pass
        
        # Clear user data and active downloads
        if user_id in user_data:
            del user_data[user_id]
        if user_id in active_downloads:
            del active_downloads[user_id]
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR in button_callback for user {user_id}: {type(e).__name__}: {error_msg}")
        await query.message.reply_text(f"❌ Download failed: {error_msg}")
        # Clear progress on error
        if user_id in download_progress:
            del download_progress[user_id]
        if user_id in user_data:
            del user_data[user_id]

def main():
    """Start the bot"""
    # Create custom request with very long timeouts for large file uploads
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=600.0,  # 10 minutes
        write_timeout=600.0,  # 10 minutes
        connect_timeout=60.0,
        pool_timeout=60.0,
    )
    
    # Create the Application with custom request and optional local Bot API server
    app_builder = Application.builder().token(BOT_TOKEN).request(request)
    
    # Use local Bot API server if configured
    if TELEGRAM_BOT_API_URL != 'https://api.telegram.org':
        app_builder.base_url(f"{TELEGRAM_BOT_API_URL}/bot")
        app_builder.base_file_url(f"{TELEGRAM_BOT_API_URL}/file/bot")
        print(f"✅ Configured to use local Bot API: {TELEGRAM_BOT_API_URL}")
    
    application = app_builder.build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    print("🤖 Bot is running...")
    print(f"📊 File size limit: {format_bytes(TELEGRAM_FILE_LIMIT)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
