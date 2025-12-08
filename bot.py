# bot.py - Main Bot File
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_USERNAME, WATERMARK_TEXT
from utils import (
    create_user_temp_dir, cleanup_user_temp, 
    get_video_duration, generate_screenshots_with_watermark,
    create_collage, create_zip_archive, format_progress_bar
)
from uploaders import upload_with_failover

# Initialize bot with increased sleep threshold
app = Client(
    "video_screenshot_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=60,
    ipv6=False
)

# User queues and locks
user_queues = {}
user_locks = {}

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text(
        f"🎬 **Video Screenshot Bot**\n\n"
        f"Send me a video and I'll create:\n"
        f"✓ Watermarked screenshots\n"
        f"✓ Cinematic collage\n"
        f"✓ ZIP archive\n\n"
        f"Powered by @{OWNER_USERNAME}"
    )

@app.on_message(filters.video | filters.document | filters.video_note)
async def handle_video(client, message: Message):
    user_id = message.from_user.id
    
    # Get video object
    video = message.video or message.document or message.video_note
    
    # Validate it's a video
    if message.document and not (message.document.mime_type and message.document.mime_type.startswith('video/')):
        await message.reply_text("❌ Please send a valid video file.")
        return
    
    # Initialize user queue and lock
    if user_id not in user_queues:
        user_queues[user_id] = []
        user_locks[user_id] = asyncio.Lock()
    
    # Add to queue
    user_queues[user_id].append({
        'message': message,
        'video': video
    })
    
    queue_position = len(user_queues[user_id])
    
    if queue_position > 1:
        await message.reply_text(
            f"⏳ Added to queue. Position: {queue_position}"
        )
    
    # Process if first in queue
    if queue_position == 1:
        asyncio.create_task(process_video_queue(client, user_id))

async def process_video_queue(client, user_id):
    """Process all videos in user's queue"""
    async with user_locks[user_id]:
        while user_queues[user_id]:
            item = user_queues[user_id][0]
            await process_single_video(client, user_id, item)
            user_queues[user_id].pop(0)

async def process_single_video(client, user_id, item):
    """Process a single video"""
    message = item['message']
    video = item['video']
    
    # Get duration
    duration = video.duration or 0
    
    # Determine screenshot count
    screenshot_count = 5 if duration < 60 else 10
    
    # Create temp directory
    user_temp_dir = create_user_temp_dir(user_id)
    video_path = os.path.join(user_temp_dir, "video.mp4")
    
    # Status message
    status_msg = await message.reply_text("⬇️ Downloading video...")
    
    try:
        # Download with progress
        last_update = [0]  # Use list to avoid UnboundLocalError
        
        async def progress(current, total):
            if total > 0 and current - last_update[0] > total * 0.05:  # Update every 5%
                progress_bar = format_progress_bar(current, total)
                try:
                    await status_msg.edit_text(
                        f"⬇️ Downloading video...\n{progress_bar}"
                    )
                    last_update[0] = current
                except:
                    pass  # Ignore flood wait errors
        
        await message.download(video_path, progress=progress)
        
        # Verify duration
        await status_msg.edit_text("🔍 Analyzing video...")
        actual_duration = await get_video_duration(video_path)
        
        if actual_duration == 0:
            await status_msg.edit_text("❌ Invalid video file.")
            cleanup_user_temp(user_id)
            return
        
        # Use actual duration for screenshot count
        screenshot_count = 5 if actual_duration < 60 else 10
        
        # Generate screenshots with watermark (single FFmpeg command)
        await status_msg.edit_text(f"📸 Generating {screenshot_count} screenshots...")
        screenshots_dir = os.path.join(user_temp_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        screenshot_files = await generate_screenshots_with_watermark(
            video_path, screenshots_dir, actual_duration, 
            screenshot_count, WATERMARK_TEXT
        )
        
        if not screenshot_files:
            await status_msg.edit_text("❌ Failed to generate screenshots.")
            cleanup_user_temp(user_id)
            return
        
        # Create collage
        await status_msg.edit_text("🎨 Creating collage...")
        collage_path = os.path.join(user_temp_dir, "collage.jpg")
        await create_collage(screenshot_files, collage_path, OWNER_USERNAME)
        
        # Create ZIP archive
        await status_msg.edit_text("📦 Creating archive...")
        zip_path = os.path.join(user_temp_dir, "screenshots.zip")
        await create_zip_archive(screenshot_files, zip_path)
        
        # Upload with failover
        await status_msg.edit_text("☁️ Uploading files...")
        
        collage_url = await upload_with_failover(
            collage_path, "collage.jpg", client, message.chat.id
        )
        zip_url = await upload_with_failover(
            zip_path, "screenshots.zip", client, message.chat.id
        )
        
        # Send final message
        final_text = (
            f"✅ **Processing Complete!**\n\n"
            f"📊 Screenshots: {len(screenshot_files)}\n"
            f"⏱️ Duration: {int(actual_duration)}s\n\n"
        )
        
        if collage_url and collage_url != "Upload failed":
            final_text += f"🖼️ [View Collage]({collage_url})\n"
        if zip_url and zip_url != "Upload failed":
            final_text += f"📦 [Download All Screenshots]({zip_url})\n"
        
        final_text += f"\n✨ Processed by @{OWNER_USERNAME}"
        
        await status_msg.edit_text(final_text, disable_web_page_preview=True)
        
    except Exception as e:
        print(f"Error processing video: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup
        cleanup_user_temp(user_id)

if __name__ == "__main__":
    print("🤖 Bot starting...")
    print(f"Bot username will be displayed after connection...")
    app.run()
