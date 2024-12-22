import os
import asyncio
import logging
from typing import List, Optional, Tuple
import tempfile
import aiohttp
import concurrent.futures
from PIL import Image, ImageDraw, ImageFont
import sys
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait
from moviepy.editor import VideoFileClip
import numpy as np
from functools import partial
import io
from concurrent.futures import ThreadPoolExecutor

# Configure logging with rotation
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            "bot.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = 28192191
API_HASH = '663164abd732848a90e76e25cb9cf54a'
BOT_TOKEN = '8151073275:AAH3KERuA23PE5DUP23LfuWS2VT5hxjH_yY'

# Constants
MAX_WORKERS = 4
MAX_QUEUE_SIZE = 50
SCREENSHOT_QUALITIES = {
    "low": 480,
    "medium": 720,
    "high": 1080
}
DEFAULT_QUALITY = "medium"

# Initialize the thread pool
thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Initialize the Pyrogram client
app = Client(
    "screenshot_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8,
    in_memory=True
)

# Queue with priority support
class PriorityQueue:
    def __init__(self, maxsize: int = 0):
        self.queue = asyncio.PriorityQueue(maxsize)
        
    async def put(self, message: Message, priority: int = 2):
        await self.queue.put((priority, message))
        
    async def get(self):
        priority, message = await self.queue.get()
        return message
        
    def empty(self):
        return self.queue.empty()

video_queue = PriorityQueue(MAX_QUEUE_SIZE)

class VideoProcessor:
    def __init__(self):
        self.session = None
        
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def close_session(self):
        if self.session:
            await self.session.close()
            
    @staticmethod
    async def extract_frame(clip: VideoFileClip, time: float, output_path: str, quality: str):
        frame = clip.get_frame(time)
        img = Image.fromarray(frame)
        target_width = SCREENSHOT_QUALITIES[quality]
        aspect_ratio = img.width / img.height
        target_height = int(target_width / aspect_ratio)
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        img.save(output_path, quality=95, optimize=True)
        return output_path

    async def generate_screenshots(
        self,
        video_path: str,
        num_screenshots: int,
        output_dir: str,
        quality: str,
        status_message: Message
    ) -> List[str]:
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            interval = duration / (num_screenshots + 1)
            screenshots = []
            
            tasks = []
            for i in range(1, num_screenshots + 1):
                time = i * interval
                screenshot_path = os.path.join(output_dir, f"screenshot_{i}.jpg")
                task = asyncio.create_task(self.extract_frame(
                    clip, time, screenshot_path, quality
                ))
                tasks.append((task, i))
                
            for task, i in tasks:
                screenshot_path = await task
                screenshots.append(screenshot_path)
                
                percent = int((i / num_screenshots) * 100)
                bar = create_progress_bar(percent)
                try:
                    await status_message.edit_text(
                        f"Generating screenshots ({quality} quality):\n{bar}"
                    )
                except (MessageNotModified, FloodWait) as e:
                    if isinstance(e, FloodWait):
                        await asyncio.sleep(e.value)
                        
            clip.close()
            return screenshots
        except Exception as e:
            logger.error(f"Error generating screenshots: {e}")
            return []

video_processor = VideoProcessor()

def get_help_text() -> str:
    return (
        "🎥 **Video Screenshot Bot Help**\n\n"
        "Here's how to use the bot:\n\n"
        "1. Send any video file to generate screenshots\n"
        "2. Use these commands:\n"
        "   • /start - Start the bot\n"
        "   • /help - Show this help message\n"
        "   • /settings - Customize screenshot settings\n\n"
        "Features:\n"
        "• Generate high-quality screenshots\n"
        "• Customize quality and number of screenshots\n"
        "• Create beautiful collages\n"
        "• Process videos up to 500MB"
    )

def create_progress_bar(percent: int) -> str:
    filled = int(percent / 10)
    return f"{'▰' * filled}{'═' * (10 - filled)} {percent}%"

async def download_video_with_progress(message: Message, file_id: str, file_path: str, status_message: Message):
    try:
        async def progress(current, total):
            percent = int((current / total) * 100)
            bar = create_progress_bar(percent)
            try:
                await status_message.edit_text(f"Downloading video:\n{bar}")
            except MessageNotModified:
                pass
            except FloodWait as e:
                await asyncio.sleep(e.value)

        await message.download(
            file_name=file_path,
            progress=progress
        )
        logger.info(f"Video download completed for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise

async def process_video(message: Message):
    video = message.video
    file_id = video.file_id
    file_name = f"{file_id}.mp4"

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, file_name)
        status_message = await message.reply_text("Initializing processing...")

        try:
            await download_video_with_progress(message, file_id, video_path, status_message)
            quality = DEFAULT_QUALITY
            screenshots = await video_processor.generate_screenshots(
                video_path, 10, temp_dir, quality, status_message
            )

            if not screenshots:
                raise Exception("Failed to generate screenshots")

            await status_message.edit_text("Creating collage...")
            collage_path = os.path.join(temp_dir, "collage.jpg")
            
            images = [Image.open(img) for img in screenshots]
            base_width = SCREENSHOT_QUALITIES[quality]
            aspect_ratio = images[0].width / images[0].height
            image_width = base_width // 3
            image_height = int(image_width / aspect_ratio)
            
            collage_width = image_width * 3
            collage_height = image_height * 4
            collage = Image.new('RGB', (collage_width, collage_height), 'white')
            
            layout = [
                (0, 0), (1, 0), (2, 0),
                (0, 1), (1, 1), (2, 1),
                (0, 2), (1, 2), (2, 2),
                (1, 3)
            ]

            for i, (img, pos) in enumerate(zip(images, layout)):
                img_resized = img.resize(
                    (image_width - 4, image_height - 4),
                    Image.Resampling.LANCZOS
                )
                
                x_pos = pos[0] * image_width + 2
                y_pos = pos[1] * image_height + 2
                
                if i == 9:
                    x_pos = (collage_width - image_width) // 2
                collage.paste(img_resized, (x_pos, y_pos))

            collage.save(collage_path, quality=95, optimize=True)

            await status_message.edit_text("Uploading collage...")

            # Upload to envs.sh
            try:
                async with aiohttp.ClientSession() as session:
                    with open(collage_path, 'rb') as f:
                        files = {'file': f}
                        async with session.post('https://envs.sh/', data=files) as response:
                            if response.status == 200:
                                share_url = await response.text()
                                # Create keyboard with share URL
                                keyboard = InlineKeyboardMarkup([[
                                    InlineKeyboardButton("View Full Size", url=share_url.strip())
                                ]])
                                
                                # Send collage to Telegram with the share URL button
                                await message.reply_photo(
                                    photo=collage_path,
                                    caption=f"Here's your collage of screenshots (Quality: {quality})\nShare link: {share_url.strip()}",
                                    reply_markup=keyboard
                                )
                            else:
                                # If envs.sh upload fails, still send the collage to Telegram
                                await message.reply_photo(
                                    photo=collage_path,
                                    caption=f"Here's your collage of screenshots (Quality: {quality})\nNote: Failed to generate share link."
                                )
            except Exception as upload_error:
                logger.error(f"Error uploading to envs.sh: {upload_error}")
                # If envs.sh upload fails, still send the collage to Telegram
                await message.reply_photo(
                    photo=collage_path,
                    caption=f"Here's your collage of screenshots (Quality: {quality})"
                )

            await status_message.delete()

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            error_msg = (
                "An error occurred while processing your video. "
                "Please make sure the video is not corrupted and try again."
            )
            await status_message.edit_text(error_msg)

async def process_video_queue():
    while True:
        try:
            if not video_queue.empty():
                message = await video_queue.get()
                try:
                    await process_video(message)
                except Exception as e:
                    logger.error(f"Error processing video: {e}")
                    await message.reply_text(
                        "An error occurred while processing your video. "
                        "Please try again later."
                    )
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in process_video_queue: {e}")
            await asyncio.sleep(5)

# Command handlers
@app.on_message(filters.command("start"))
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Help", callback_data="help"),
            InlineKeyboardButton("Settings", callback_data="settings")
        ]
    ])
    await message.reply_text(
        "Welcome! I'm the Enhanced Screenshot Bot. Send me a video, and I'll generate "
        "high-quality screenshots for you. You can customize the number of screenshots "
        "and quality settings.",
        reply_markup=keyboard
    )

@app.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply_text(get_help_text())

@app.on_message(filters.command("settings"))
async def settings_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Low Quality", callback_data="quality_low"),
            InlineKeyboardButton("Medium Quality", callback_data="quality_medium"),
            InlineKeyboardButton("High Quality", callback_data="quality_high")
        ],
        [
            InlineKeyboardButton("5 Screenshots", callback_data="count_5"),
            InlineKeyboardButton("10 Screenshots", callback_data="count_10"),
            InlineKeyboardButton("15 Screenshots", callback_data="count_15")
        ]
    ])
    await message.reply_text(
        "Choose your preferred settings:",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    if data == "help":
        await callback_query.message.reply_text(get_help_text())
    elif data == "settings":
        await settings_command(client, callback_query.message)
    elif data.startswith("quality_"):
        quality = data.split("_")[1]
        await callback_query.answer(f"Quality set to {quality}")
    elif data.startswith("count_"):
        count = int(data.split("_")[1])
        await callback_query.answer(f"Screenshot count set to {count}")

@app.on_message(filters.video)
async def handle_video(client, message):
    try:
        if video_queue.queue.qsize() >= MAX_QUEUE_SIZE:
            await message.reply_text(
                "The bot is currently processing too many videos. Please try again later."
            )
            return

        video = message.video
        duration = video.duration
        file_size = video.file_size

        if duration > 3600:
            await message.reply_text(
                "Video is too long. Please send a video shorter than 1 hour."
            )
            return
        
        if file_size > 500 * 1024 * 1024:
            await message.reply_text(
                "Video file is too large. Please send a video smaller than 500MB."
            )
            return

        status_message = await message.reply_text(
            "Video added to queue. Processing will begin shortly.\n"
            f"Queue position: {video_queue.queue.qsize() + 1}"
        )

        priority = 1 if file_size < 50 * 1024 * 1024 else 2
        await video_queue.put(message, priority)

    except Exception as e:
        logger.error(f"Error handling video: {e}")
        await message.reply_text("An error occurred while processing your request.")

async def main():
    await video_processor.init_session()
    await app.start()
    logger.info("Bot started. Processing queue initialized...")
    
    queue_processor = asyncio.create_task(process_video_queue())
    
    try:
        await idle()
    finally:
        queue_processor.cancel()
        await video_processor.close_session()
        await app.stop()

if __name__ == "__main__":
    app.run(main())
