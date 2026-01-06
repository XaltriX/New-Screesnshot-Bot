"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    LINKZ SCREENSHOT BOT - Ultimate Version
    Owner: @NeonGhost
    Powered by: @Linkz_Wallah
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import math
import asyncio
import hashlib
import logging
import tempfile
import datetime
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from logging.handlers import RotatingFileHandler

import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait
from moviepy.editor import VideoFileClip

# ═══════════════════════════════════════════════════════════════════
# SECTION 1: LOGGING SETUP (WINDOWS COMPATIBLE)
# ═══════════════════════════════════════════════════════════════════

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SECTION 2: CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

class Config:
    # Bot Credentials
    API_ID = 24955235
    API_HASH = 'f317b3f7bbe390346d8b46868cff0de8'
    BOT_TOKEN = '8151073275:AAEF_R2c7ZyN-c4t3gt4NdcHpa3AD5Qdm6k'
    
    # Owner
    OWNER_USERNAME = "NeonGhost"
    OWNER_USER_ID = None
    
    # Watermark
    WATERMARK_TEXT = "BY @Linkz_Wallah"
    WATERMARK_FONT_SIZE = 48
    
    # Upload APIs
    CATBOX_API = "https://catbox.moe/user/api.php"
    ENVS_API = "https://envs.sh"
    TELEGRAPH_API = "https://telegra.ph/upload"
    
    # Collage Settings
    COLLAGE_BACKGROUND = "#000000"
    FRAME_BORDER = 10
    FRAME_SPACING = 15
    
    # Quality Settings
    QUALITIES = {"low": 480, "medium": 720, "high": 1080}
    DEFAULT_QUALITY = "medium"
    
    # Limits
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_DURATION = 3600  # 1 hour
    
    # Paths
    DB_PATH = "bot_data.db"
    TEMP_DIR = "temp_downloads"
    
    # Grid Layouts
    GRID_LAYOUTS = {
        4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3),
        10: (2, 5), 12: (3, 4), 15: (3, 5)
    }

os.makedirs(Config.TEMP_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# SECTION 3: PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════

class ProgressBar:
    @staticmethod
    def create(percentage: int, length: int = 10, style: str = "hearts") -> str:
        filled = int((percentage / 100) * length)
        empty = length - filled
        
        if style == "hearts":
            bar = "♥" * filled + "♡" * empty
        else:
            bar = "█" * filled + "░" * empty
        
        return f"{bar} {percentage}%"
    
    @staticmethod
    def download(current: int, total: int) -> str:
        percentage = int((current / total) * 100) if total > 0 else 0
        bar = ProgressBar.create(percentage)
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        return f"⬇️ **Downloading Video**\n\n{bar}\n{current_mb:.1f} / {total_mb:.1f} MB"
    
    @staticmethod
    def extraction(current: int, total: int, elapsed: int) -> str:
        percentage = int((current / total) * 100) if total > 0 else 0
        bar = ProgressBar.create(percentage)
        return f"📸 **Extracting Screenshots**\n\n{bar}\n{current}/{total} • {elapsed}s elapsed"
    
    @staticmethod
    def upload(service: str, status: str) -> str:
        return f"☁️ **Uploading to Cloud**\n\n{service}: {status}"

# ═══════════════════════════════════════════════════════════════════
# SECTION 4: MESSAGES
# ═══════════════════════════════════════════════════════════════════

class Messages:
    UNAUTHORIZED = """
🚫 **Access Denied**

This bot is private and restricted to authorized users only.

👤 Owner: @{owner}
💬 Want your own bot? Contact @{owner}

━━━━━━━━━━━━━━━━
_Thank you for your interest!_
"""

    START = """
🎬 **Screenshot Collage Bot**

Welcome! Send me a video and I'll create a beautiful cinematic collage!

━━━━━━━━━━━━━━━━

**✨ Features:**
• Cinematic film-strip style
• Multiple cloud uploads (Catbox, EnvS, Telegraph)
• Smart caching for faster results
• Live progress tracking
• Automatic watermark

━━━━━━━━━━━━━━━━
_Powered by @Linkz_Wallah_
"""

    HELP = """
📖 **How to Use**

1️⃣ Send any video file (max 500MB)
2️⃣ Choose number of screenshots (4-15)
3️⃣ Wait for processing with live updates
4️⃣ Get your collage with multiple download links!

━━━━━━━━━━━━━━━━

**Commands:**
/start - Start the bot
/help - Show this help
/stats - View your statistics
/quality - Change quality settings

━━━━━━━━━━━━━━━━
"""

    QUEUE_ADDED = """
🎬 **Video Added to Queue**

📊 Position: #{position}
⏱️ Estimated wait: ~{wait_time}

━━━━━━━━━━━━━━━━
_Processing will start automatically..._
"""

    SUCCESS = """
✅ **Collage Ready!**

📸 Screenshots: {count}
💾 Size: {size} MB
⏱️ Time: {duration}s
🎨 Quality: {quality}

━━━━━━━━━━━━━━━━

📥 **Download Links:**

{links}

━━━━━━━━━━━━━━━━
_Powered by @Linkz_Wallah_
"""

    ERROR = "❌ **Error:** {error}\n\n_Contact @{owner} if this persists._"
    
    VIDEO_TOO_LARGE = "❌ Video too large! Max size: 500MB\nYour video: {size}MB"
    VIDEO_TOO_LONG = "❌ Video too long! Max duration: 1 hour\nYour video: {duration} min"

# ═══════════════════════════════════════════════════════════════════
# SECTION 5: DATABASE
# ═══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_owner BOOLEAN DEFAULT 0,
                quality TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                video_hash TEXT PRIMARY KEY,
                catbox_link TEXT,
                envs_link TEXT,
                telegraph_link TEXT,
                screenshot_count INTEGER,
                quality TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                user_id INTEGER PRIMARY KEY,
                total_screenshots INTEGER DEFAULT 0,
                total_videos INTEGER DEFAULT 0,
                total_time INTEGER DEFAULT 0,
                storage_mb REAL DEFAULT 0
            )
        """)
        
        self.conn.commit()
    
    def is_owner(self, user_id: int, username: str) -> bool:
        if Config.OWNER_USER_ID and user_id == Config.OWNER_USER_ID:
            return True
        if username and username.lower() == Config.OWNER_USERNAME.lower():
            if not Config.OWNER_USER_ID:
                Config.OWNER_USER_ID = user_id
            return True
        return False
    
    def get_user_quality(self, user_id: int) -> str:
        self.cursor.execute("SELECT quality FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row[0] if row else Config.DEFAULT_QUALITY
    
    def set_user_quality(self, user_id: int, quality: str):
        self.cursor.execute("""
            INSERT INTO users (user_id, quality) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET quality = ?
        """, (user_id, quality, quality))
        self.conn.commit()
    
    def get_cached_links(self, video_hash: str) -> Optional[Dict]:
        self.cursor.execute("""
            SELECT catbox_link, envs_link, telegraph_link, screenshot_count, quality
            FROM cache WHERE video_hash = ?
        """, (video_hash,))
        row = self.cursor.fetchone()
        if row:
            return {
                'catbox': row[0], 'envs': row[1], 'telegraph': row[2],
                'count': row[3], 'quality': row[4]
            }
        return None
    
    def cache_links(self, video_hash: str, links: Dict, count: int, quality: str):
        self.cursor.execute("""
            INSERT OR REPLACE INTO cache 
            (video_hash, catbox_link, envs_link, telegraph_link, screenshot_count, quality)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (video_hash, links.get('catbox'), links.get('envs'), 
              links.get('telegraph'), count, quality))
        self.conn.commit()
    
    def update_analytics(self, user_id: int, screenshots: int, time_taken: int, size_mb: float):
        self.cursor.execute("""
            INSERT INTO analytics (user_id, total_screenshots, total_videos, total_time, storage_mb)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                total_screenshots = total_screenshots + ?,
                total_videos = total_videos + 1,
                total_time = total_time + ?,
                storage_mb = storage_mb + ?
        """, (user_id, screenshots, time_taken, size_mb, screenshots, time_taken, size_mb))
        self.conn.commit()
    
    def get_user_stats(self, user_id: int) -> Dict:
        self.cursor.execute("""
            SELECT total_screenshots, total_videos, total_time, storage_mb
            FROM analytics WHERE user_id = ?
        """, (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'screenshots': row[0], 'videos': row[1],
                'time': row[2], 'storage': row[3]
            }
        return {'screenshots': 0, 'videos': 0, 'time': 0, 'storage': 0}

db = Database()

# ═══════════════════════════════════════════════════════════════════
# SECTION 6: VIDEO PROCESSOR (MOVIEPY BASED)
# ═══════════════════════════════════════════════════════════════════

class VideoProcessor:
    @staticmethod
    def generate_hash(file_id: str, file_size: int) -> str:
        return hashlib.md5(f"{file_id}_{file_size}".encode()).hexdigest()
    
    @staticmethod
    async def extract_screenshots(
        video_path: str,
        num_screenshots: int,
        quality: str,
        status_msg: Message,
        safe_edit
    ) -> List[str]:
        screenshots = []
        
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            interval = duration / (num_screenshots + 1)
            
            start_time = time.time()
            
            for i in range(1, num_screenshots + 1):
                timestamp = i * interval
                frame = clip.get_frame(timestamp)
                
                img = Image.fromarray(frame)
                target_width = Config.QUALITIES[quality]
                aspect_ratio = img.width / img.height
                target_height = int(target_width / aspect_ratio)
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                screenshot_path = os.path.join(Config.TEMP_DIR, f"shot_{int(time.time())}_{i}.jpg")
                img.save(screenshot_path, quality=95, optimize=True)
                screenshots.append((screenshot_path, timestamp))
                
                elapsed = int(time.time() - start_time)
                progress_text = ProgressBar.extraction(i, num_screenshots, elapsed)
                await safe_edit(status_msg, progress_text)
            
            clip.close()
            return screenshots
            
        except Exception as e:
            log.error(f"Screenshot extraction error: {e}")
            return []

# ═══════════════════════════════════════════════════════════════════
# SECTION 7: COLLAGE CREATOR
# ═══════════════════════════════════════════════════════════════════

class CollageCreator:
    @staticmethod
    def create_cinematic_collage(
        screenshots: List[tuple],
        output_path: str
    ) -> bool:
        try:
            num_shots = len(screenshots)
            
            if num_shots in Config.GRID_LAYOUTS:
                rows, cols = Config.GRID_LAYOUTS[num_shots]
            else:
                cols = math.ceil(math.sqrt(num_shots))
                rows = math.ceil(num_shots / cols)
            
            first_img = Image.open(screenshots[0][0])
            img_width, img_height = first_img.size
            
            target_width = 1280
            target_height = int(img_height * (target_width / img_width))
            
            border = Config.FRAME_BORDER
            spacing = Config.FRAME_SPACING
            
            collage_width = (target_width * cols) + (spacing * (cols + 1)) + (border * 2)
            collage_height = (target_height * rows) + (spacing * (rows + 1)) + (border * 2)
            
            collage = Image.new('RGB', (collage_width, collage_height), Config.COLLAGE_BACKGROUND)
            draw = ImageDraw.Draw(collage)
            
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 30)
                wm_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", Config.WATERMARK_FONT_SIZE)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
                    wm_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", Config.WATERMARK_FONT_SIZE)
                except:
                    font = ImageFont.load_default()
                    wm_font = font
            
            for idx, (img_path, timestamp) in enumerate(screenshots[:num_shots]):
                row = idx // cols
                col = idx % cols
                
                img = Image.open(img_path)
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                x = border + spacing + (col * (target_width + spacing))
                y = border + spacing + (row * (target_height + spacing))
                
                collage.paste(img, (x, y))
                
                time_str = str(datetime.timedelta(seconds=int(timestamp)))
                text_bbox = draw.textbbox((0, 0), time_str, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                text_bg_x = x + 10
                text_bg_y = y + target_height - text_height - 20
                
                overlay = Image.new('RGBA', collage.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rectangle(
                    [text_bg_x - 5, text_bg_y - 5,
                     text_bg_x + text_width + 5, text_bg_y + text_height + 5],
                    fill=(0, 0, 0, 180)
                )
                collage = Image.alpha_composite(collage.convert('RGBA'), overlay).convert('RGB')
                draw = ImageDraw.Draw(collage)
                
                draw.text((text_bg_x, text_bg_y), time_str, font=font, fill='white')
            
            watermark = Config.WATERMARK_TEXT
            wm_bbox = draw.textbbox((0, 0), watermark, font=wm_font)
            wm_width = wm_bbox[2] - wm_bbox[0]
            wm_height = wm_bbox[3] - wm_bbox[1]
            
            wm_x = collage_width - wm_width - 30
            wm_y = collage_height - wm_height - 30
            
            overlay = Image.new('RGBA', collage.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [wm_x - 10, wm_y - 10, wm_x + wm_width + 10, wm_y + wm_height + 10],
                fill=(0, 0, 0, int(255 * 0.7))
            )
            collage = Image.alpha_composite(collage.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(collage)
            
            draw.text((wm_x, wm_y), watermark, font=wm_font, fill='white')
            
            collage.save(output_path, quality=95, optimize=True)
            return True
            
        except Exception as e:
            log.error(f"Collage creation error: {e}")
            return False

# ═══════════════════════════════════════════════════════════════════
# SECTION 8: CLOUD UPLOADER
# ═══════════════════════════════════════════════════════════════════

class CloudUploader:
    @staticmethod
    async def upload_to_catbox(file_path: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('reqtype', 'fileupload')
                    data.add_field('fileToUpload', f)
                    
                    async with session.post(Config.CATBOX_API, data=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            return (await resp.text()).strip()
        except Exception as e:
            log.error(f"Catbox upload failed: {e}")
        return None
    
    @staticmethod
    async def upload_to_envs(file_path: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f)
                    
                    async with session.post(Config.ENVS_API, data=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            return (await resp.text()).strip()
        except Exception as e:
            log.error(f"EnvS upload failed: {e}")
        return None
    
    @staticmethod
    async def upload_to_telegraph(file_path: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f)
                    
                    async with session.post(Config.TELEGRAPH_API, data=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if result and len(result) > 0:
                                return f"https://telegra.ph{result[0]['src']}"
        except Exception as e:
            log.error(f"Telegraph upload failed: {e}")
        return None
    
    @staticmethod
    async def multi_upload(file_path: str, status_msg: Message, safe_edit) -> Dict[str, Optional[str]]:
        links = {}
        
        await safe_edit(status_msg, ProgressBar.upload("Catbox", "Uploading..."))
        links['catbox'] = await CloudUploader.upload_to_catbox(file_path)
        
        await safe_edit(status_msg, ProgressBar.upload("EnvS", "Uploading..."))
        links['envs'] = await CloudUploader.upload_to_envs(file_path)
        
        await safe_edit(status_msg, ProgressBar.upload("Telegraph", "Uploading..."))
        links['telegraph'] = await CloudUploader.upload_to_telegraph(file_path)
        
        return links

# ═══════════════════════════════════════════════════════════════════
# SECTION 9: MAIN PROCESSOR
# ═══════════════════════════════════════════════════════════════════

class MainProcessor:
    @staticmethod
    async def process_video(message: Message, video_msg: Message, num_screenshots: int):
        start_time = time.time()
        video_path = None
        last_text = ""
        
        async def safe_edit(msg: Message, text: str):
            nonlocal last_text
            if text != last_text:
                try:
                    await msg.edit(text)
                    last_text = text
                except (MessageNotModified, FloodWait) as e:
                    if isinstance(e, FloodWait):
                        await asyncio.sleep(e.value)
                except Exception as e:
                    if "MESSAGE_NOT_MODIFIED" not in str(e):
                        log.error(f"Edit error: {e}")
        
        try:
            video = video_msg.video
            video_hash = VideoProcessor.generate_hash(video.file_id, video.file_size)
            quality = db.get_user_quality(video_msg.from_user.id)
            
            cached = db.get_cached_links(video_hash)
            if cached and any([cached.get('catbox'), cached.get('envs'), cached.get('telegraph')]):
                await safe_edit(message, "⚡ **Cached Result Found!**\n\nSending saved links...")
                await asyncio.sleep(1)
                
                links_text = MainProcessor._format_links(cached)
                await video_msg.reply_text(
                    Messages.SUCCESS.format(
                        count=cached['count'],
                        size="Cached",
                        duration=int(time.time() - start_time),
                        quality=cached['quality'],
                        links=links_text
                    )
                )
                await message.delete()
                return
            
            video_path = os.path.join(Config.TEMP_DIR, f"video_{int(time.time())}.mp4")
            
            last_update = [time.time()]
            last_pct = [-1]
            
            async def progress(current, total):
                pct = int((current / total) * 100) if total > 0 else 0
                if (pct - last_pct[0] >= 5) or (time.time() - last_update[0] >= 3):
                    await safe_edit(message, ProgressBar.download(current, total))
                    last_update[0] = time.time()
                    last_pct[0] = pct
            
            await video_msg.download(file_name=video_path, progress=progress)
            
            await safe_edit(message, "🎬 **Analyzing video...**")
            
            screenshots = await VideoProcessor.extract_screenshots(
                video_path, num_screenshots, quality, message, safe_edit
            )
            
            if not screenshots:
                await safe_edit(message, Messages.ERROR.format(
                    error="Failed to extract screenshots",
                    owner=Config.OWNER_USERNAME
                ))
                return
            
            await safe_edit(message, "🎨 **Creating cinematic collage...**")
            
            collage_path = os.path.join(Config.TEMP_DIR, f"collage_{int(time.time())}.jpg")
            success = CollageCreator.create_cinematic_collage(screenshots, collage_path)
            
            if not success:
                await safe_edit(message, Messages.ERROR.format(
                    error="Collage creation failed",
                    owner=Config.OWNER_USERNAME
                ))
                return
            
            links = await CloudUploader.multi_upload(collage_path, message, safe_edit)
            
            if not any(links.values()):
                await safe_edit(message, Messages.ERROR.format(
                    error="All uploads failed",
                    owner=Config.OWNER_USERNAME
                ))
                return
            
            db.cache_links(video_hash, links, len(screenshots), quality)
            
            file_size_mb = os.path.getsize(collage_path) / (1024 * 1024)
            process_time = int(time.time() - start_time)
            db.update_analytics(video_msg.from_user.id, len(screenshots), process_time, file_size_mb)
            
            links_text = MainProcessor._format_links(links)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Catbox", url=links['catbox'])] if links.get('catbox') else [],
                [InlineKeyboardButton("🔗 EnvS", url=links['envs'])] if links.get('envs') else [],
                [InlineKeyboardButton("🔗 Telegraph", url=links['telegraph'])] if links.get('telegraph') else [],
            ])
            
            await video_msg.reply_photo(
                photo=collage_path,
                caption=Messages.SUCCESS.format(
                    count=len(screenshots),
                    size=f"{file_size_mb:.2f}",
                    duration=process_time,
                    quality=quality,
                    links=links_text
                ),
                reply_markup=keyboard if any(links.values()) else None
            )
            
            await message.delete()
            
            for img_path, _ in screenshots:
                try:
                    os.remove(img_path)
                except:
                    pass
            try:
                os.remove(collage_path)
            except:
                pass
            
        except Exception as e:
            log.error(f"Processing error: {e}", exc_info=True)
            error_msg = str(e)
            if "timed out" in error_msg.lower():
                error_msg = "Download timeout. Try a smaller video or check your connection."
            await safe_edit(message, Messages.ERROR.format(
                error=error_msg[:100],
                owner=Config.OWNER_USERNAME
            ))
        finally:
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
    
    @staticmethod
    def _format_links(links: Dict) -> str:
        parts = []
        if links.get('catbox'):
            parts.append(f"🔗 [Catbox]({links['catbox']})")
        if links.get('envs'):
            parts.append(f"🔗 [EnvS]({links['envs']})")
        if links.get('telegraph'):
            parts.append(f"🔗 [Telegraph]({links['telegraph']})")
        return "\n".join(parts) if parts else "No links available"

# ═══════════════════════════════════════════════════════════════════
# SECTION 10: PYROGRAM CLIENT
# ═══════════════════════════════════════════════════════════════════

app = Client(
    "linkz_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=8
)

user_videos = {}

def authorized_only(func):
    async def wrapper(client: Client, message: Message):
        user = message.from_user
        if not db.is_owner(user.id,
