"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    LINKZ SCREENSHOT BOT - Complete with Queue System
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
from typing import Optional, List, Dict, Tuple
from logging.handlers import RotatingFileHandler

import aiohttp
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait

try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("⚠️ MoviePy not available, using FFmpeg only")

# ═══════════════════════════════════════════════════════════════════
# LOGGING SETUP
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
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

class Config:
    API_ID = int(os.getenv("API_ID", "24955235"))
    API_HASH = os.getenv("API_HASH", "f317b3f7bbe390346d8b46868cff0de8")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8151073275:AAG1GNMQaeiffKpzszeimnK9C9R0Uro-yxc")
    
    OWNER_USERNAME = os.getenv("OWNER_USERNAME", "NeonGhost")
    OWNER_USER_ID = None
    
    WATERMARK_TEXT = "BY @Linkz_Wallah"
    WATERMARK_FONT_SIZE = 60
    WATERMARK_PADDING = 20
    
    CATBOX_API = "https://catbox.moe/user/api.php"
    TELEGRAPH_API = "https://telegra.ph/upload"
    
    COLLAGE_BACKGROUND = "#000000"
    FRAME_BORDER = 20
    FRAME_SPACING = 5
    IMAGE_PADDING = 0
    
    QUALITIES = {"low": 640, "medium": 960, "high": 1280}
    DEFAULT_QUALITY = "medium"
    
    MAX_VIDEO_SIZE = 500 * 1024 * 1024
    MAX_DURATION = 3600
    
    DB_PATH = "bot_data.db"
    TEMP_DIR = "./temp_downloads"
    
    GRID_LAYOUTS = {
        4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3),
        10: (2, 5), 12: (3, 4), 15: (3, 5)
    }
    
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"

os.makedirs(Config.TEMP_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# PROGRESS BAR
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
    def upload(service: str, current: int, total: int) -> str:
        percentage = int((current / total) * 100) if total > 0 else 0
        bar = ProgressBar.create(percentage)
        return f"☁️ **Uploading to Cloud**\n\n{service}: {bar}"

# ═══════════════════════════════════════════════════════════════════
# QUEUE SYSTEM
# ═══════════════════════════════════════════════════════════════════

class VideoQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.processing = False
        self.current_item = None
    
    async def add(self, video_msg: Message, num_screenshots: int, user_id: int):
        queue_item = {
            'video_msg': video_msg,
            'num_screenshots': num_screenshots,
            'user_id': user_id,
            'filename': getattr(video_msg.video or video_msg.document, 'file_name', 'video.mp4'),
            'position': self.queue.qsize() + 1,
            'added_at': time.time()
        }
        await self.queue.put(queue_item)
        return queue_item['position']
    
    def get_position(self, user_id: int) -> int:
        return self.queue.qsize()
    
    def is_empty(self) -> bool:
        return self.queue.empty()
    
    async def get_next(self):
        if not self.queue.empty():
            self.current_item = await self.queue.get()
            return self.current_item
        return None
    
    def task_done(self):
        self.queue.task_done()
        self.current_item = None

video_queue = VideoQueue()

# ═══════════════════════════════════════════════════════════════════
# MESSAGES
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
• Multi-cloud uploads (Catbox, Telegraph)
• Smart caching
• Queue system
• Live progress tracking

**📊 Limits:**
• Max size: 500MB
• Max duration: 1 hour

━━━━━━━━━━━━━━━━
_Powered by @Linkz_Wallah_
"""

    HELP = """
📖 **How to Use**

1️⃣ Send any video file
2️⃣ Choose screenshot count (4-15)
3️⃣ Wait for processing (queue system)
4️⃣ Get your collage!

━━━━━━━━━━━━━━━━

**Commands:**
/start - Start the bot
/help - Show this help
/stats - View statistics
/quality - Change quality

━━━━━━━━━━━━━━━━
"""

    SUCCESS = """
✅ **Collage Ready!**

📹 Video: {filename}
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

    QUEUE_ADDED = """
🎬 **Added to Queue**

📹 Video: {filename}
📊 Queue Position: #{position}
⏱️ Estimated Wait: ~{wait_time}

━━━━━━━━━━━━━━━━
_You'll be notified when processing starts_
"""

    QUEUE_PROCESSING = """
⚙️ **Processing Started**

📹 Video: {filename}
📊 Queue: {current}/{total}

━━━━━━━━━━━━━━━━
"""

    ERROR = "❌ **Error:** {error}\n\n_Contact @{owner} if this persists._"
    VIDEO_TOO_LARGE = "❌ Video too large!\n\nMax: 500MB\nYour video: {size}MB"
    VIDEO_TOO_LONG = "❌ Video too long!\n\nMax: 1 hour\nYour video: {duration} min"
    CACHE_HIT = "⚡ **Cached Result!**\n\nSending saved links instantly..."

# ═══════════════════════════════════════════════════════════════════
# DATABASE
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
                self.cursor.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, is_owner) VALUES (?, ?, 1)",
                    (user_id, username)
                )
                self.conn.commit()
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
            SELECT catbox_link, telegraph_link, screenshot_count, quality
            FROM cache WHERE video_hash = ?
        """, (video_hash,))
        row = self.cursor.fetchone()
        if row:
            return {
                'catbox': row[0], 'telegraph': row[1],
                'count': row[2], 'quality': row[3]
            }
        return None
    
    def cache_links(self, video_hash: str, links: Dict, count: int, quality: str):
        self.cursor.execute("""
            INSERT OR REPLACE INTO cache 
            (video_hash, catbox_link, telegraph_link, screenshot_count, quality)
            VALUES (?, ?, ?, ?, ?)
        """, (video_hash, links.get('catbox'), links.get('telegraph'), count, quality))
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
# SECTION 6: VIDEO PROCESSOR
# ═══════════════════════════════════════════════════════════════════

class VideoProcessor:
    @staticmethod
    def generate_hash(file_id: str, file_size: int) -> str:
        return hashlib.md5(f"{file_id}_{file_size}".encode()).hexdigest()
    
    @staticmethod
    async def get_video_info(video_path: str) -> Optional[float]:
        """Get video duration using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            log.info(f"Getting duration...")
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                duration = float(stdout.decode().strip())
                log.info(f"Video duration: {duration:.2f}s")
                return duration
            
            if stderr:
                log.error(f"FFprobe error: {stderr.decode()[:200]}")
            
        except FileNotFoundError:
            log.error("FFprobe command not found!")
        except Exception as e:
            log.error(f"Error getting duration: {e}")
        
        return None
    
    @staticmethod
    async def extract_screenshots_ffmpeg(
        video_path: str,
        num_screenshots: int,
        quality: str,
        status_msg: Message,
        safe_edit
    ) -> List[Tuple[str, float]]:
        """Extract screenshots using FFmpeg"""
        screenshots = []
        
        try:
            duration = await VideoProcessor.get_video_info(video_path)
            if not duration:
                log.error("Could not get video duration")
                return []
            
            interval = duration / (num_screenshots + 1)
            target_width = Config.QUALITIES[quality]
            start_time = time.time()
            
            for i in range(1, num_screenshots + 1):
                timestamp = i * interval
                screenshot_path = os.path.join(
                    Config.TEMP_DIR,
                    f"shot_{int(time.time())}_{i}.jpg"
                )
                
                cmd = [
                    "ffmpeg",
                    '-ss', str(timestamp),
                    '-i', video_path,
                    '-vf', f'scale={target_width}:-1',
                    '-vframes', '1',
                    '-q:v', '2',
                    '-y',
                    screenshot_path
                ]
                
                log.info(f"Extracting screenshot {i}/{num_screenshots} at {timestamp:.1f}s")
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if os.path.exists(screenshot_path):
                    screenshots.append((screenshot_path, timestamp))
                    
                    elapsed = int(time.time() - start_time)
                    progress_text = ProgressBar.extraction(i, num_screenshots, elapsed)
                    await safe_edit(status_msg, progress_text)
                else:
                    log.error(f"Screenshot {i} failed")
                    if stderr:
                        error_text = stderr.decode()[:300]
                        log.error(f"FFmpeg error: {error_text}")
            
            log.info(f"Successfully extracted {len(screenshots)}/{num_screenshots} screenshots")
            return screenshots
            
        except FileNotFoundError:
            log.error("FFmpeg command not found!")
            return []
        except Exception as e:
            log.error(f"FFmpeg extraction error: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def extract_screenshots(
        video_path: str,
        num_screenshots: int,
        quality: str,
        status_msg: Message,
        safe_edit
    ) -> List[Tuple[str, float]]:
        """Main extraction method"""
        
        # Use FFmpeg (MoviePy not needed for Heroku)
        log.info("Using FFmpeg for extraction")
        screenshots = await VideoProcessor.extract_screenshots_ffmpeg(
            video_path, num_screenshots, quality, status_msg, safe_edit
        )
        
        if screenshots:
            return screenshots
        
        log.error("Screenshot extraction failed")
        return []

# ═══════════════════════════════════════════════════════════════════
# SECTION 7: COLLAGE CREATOR
# ═══════════════════════════════════════════════════════════════════

class CollageCreator:
    @staticmethod
    def create_cinematic_collage(
        screenshots: List[Tuple[str, float]],
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
            
            target_collage_width = 3000
            target_width = (target_collage_width - (Config.FRAME_SPACING * (cols + 1)) - (Config.FRAME_BORDER * 2)) // cols
            target_height = int(target_width * (img_height / img_width))
            
            border = Config.FRAME_BORDER
            spacing = Config.FRAME_SPACING
            
            collage_width = (target_width * cols) + (spacing * (cols + 1)) + (border * 2)
            collage_height = (target_height * rows) + (spacing * (rows + 1)) + (border * 2)
            
            log.info(f"Collage: {collage_width}x{collage_height}, Frame: {target_width}x{target_height}")
            
            collage = Image.new('RGB', (collage_width, collage_height), Config.COLLAGE_BACKGROUND)
            draw = ImageDraw.Draw(collage)
            
            try:
                if sys.platform == 'win32':
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 36)
                    wm_font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", Config.WATERMARK_FONT_SIZE)
                else:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
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
                
                text_bg_x = x + 15
                text_bg_y = y + target_height - text_height - 25
                
                overlay = Image.new('RGBA', collage.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rectangle(
                    [text_bg_x - 8, text_bg_y - 5,
                     text_bg_x + text_width + 8, text_bg_y + text_height + 5],
                    fill=(0, 0, 0, 200)
                )
                collage = Image.alpha_composite(collage.convert('RGBA'), overlay).convert('RGB')
                draw = ImageDraw.Draw(collage)
                
                draw.text((text_bg_x, text_bg_y), time_str, font=font, fill='white')
            
            watermark = Config.WATERMARK_TEXT
            wm_bbox = draw.textbbox((0, 0), watermark, font=wm_font)
            wm_width = wm_bbox[2] - wm_bbox[0]
            wm_height = wm_bbox[3] - wm_bbox[1]
            
            wm_x = collage_width - wm_width - Config.WATERMARK_PADDING - border
            wm_y = collage_height - wm_height - Config.WATERMARK_PADDING - border
            
            overlay = Image.new('RGBA', collage.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [wm_x - 15, wm_y - 10, wm_x + wm_width + 15, wm_y + wm_height + 10],
                fill=(0, 0, 0, 180)
            )
            collage = Image.alpha_composite(collage.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(collage)
            
            draw.text((wm_x, wm_y), watermark, font=wm_font, fill='white')
            
            collage.save(output_path, quality=95, optimize=True)
            
            log.info(f"Collage saved: {os.path.getsize(output_path) / (1024*1024):.2f}MB")
            return True
            
        except Exception as e:
            log.error(f"Collage creation error: {e}", exc_info=True)
            return False
# ═══════════════════════════════════════════════════════════════════
# SECTION 8: CLOUD UPLOADER (CATBOX + TELEGRAPH ONLY)
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
                    
                    timeout = aiohttp.ClientTimeout(total=180)
                    async with session.post(Config.CATBOX_API, data=data, timeout=timeout) as resp:
                        if resp.status == 200:
                            url = (await resp.text()).strip()
                            log.info(f"Catbox upload success: {url}")
                            return url
                        log.error(f"Catbox upload failed: HTTP {resp.status}")
        except Exception as e:
            log.error(f"Catbox upload error: {e}")
        return None
    
    @staticmethod
    async def upload_to_telegraph(file_path: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f)
                    
                    timeout = aiohttp.ClientTimeout(total=180)
                    async with session.post(Config.TELEGRAPH_API, data=data, timeout=timeout) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if result and len(result) > 0:
                                url = f"https://telegra.ph{result[0]['src']}"
                                log.info(f"Telegraph upload success: {url}")
                                return url
                        log.error(f"Telegraph upload failed: HTTP {resp.status}")
        except Exception as e:
            log.error(f"Telegraph upload error: {e}")
        return None
    
    @staticmethod
    async def multi_upload(file_path: str, status_msg: Message, safe_edit) -> Dict[str, Optional[str]]:
        links = {}
        services = [
            ('Catbox', CloudUploader.upload_to_catbox),
            ('Telegraph', CloudUploader.upload_to_telegraph)
        ]
        
        for idx, (name, upload_func) in enumerate(services, 1):
            await safe_edit(status_msg, ProgressBar.upload(name, idx - 1, len(services)))
            
            link = await upload_func(file_path)
            if link:
                links[name.lower()] = link
            
            await safe_edit(status_msg, ProgressBar.upload(name, idx, len(services)))
        
        log.info(f"Upload results: {links}")
        return links

# ═══════════════════════════════════════════════════════════════════
# SECTION 9: MAIN PROCESSOR
# ═══════════════════════════════════════════════════════════════════

class MainProcessor:
    @staticmethod
    async def process_video(status_msg: Message, video_msg: Message, num_screenshots: int, queue_position: int, queue_total: int):
        start_time = time.time()
        video_path = None
        collage_path = None
        screenshot_files = []
        last_text = ""
        
        # Get video info
        video = video_msg.video or video_msg.document
        filename = getattr(video, 'file_name', 'video.mp4')
        
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
            video_hash = VideoProcessor.generate_hash(video.file_id, video.file_size)
            quality = db.get_user_quality(video_msg.from_user.id)
            
            # Show processing status
            await safe_edit(
                status_msg,
                Messages.QUEUE_PROCESSING.format(
                    filename=filename,
                    current=queue_position,
                    total=queue_total
                )
            )
            
            # Check cache
            cached = db.get_cached_links(video_hash)
            if cached and any([cached.get('catbox'), cached.get('telegraph')]):
                await safe_edit(status_msg, Messages.CACHE_HIT)
                await asyncio.sleep(1)
                
                links_text = MainProcessor._format_links(cached)
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Catbox", url=cached['catbox'])] if cached.get('catbox') else [],
                    [InlineKeyboardButton("🔗 Telegraph", url=cached['telegraph'])] if cached.get('telegraph') else [],
                ])
                
                # Reply to original video
                await video_msg.reply_text(
                    Messages.SUCCESS.format(
                        filename=filename,
                        count=cached['count'],
                        size="Cached",
                        duration=int(time.time() - start_time),
                        quality=cached['quality'],
                        links=links_text
                    ),
                    reply_markup=keyboard if any([cached.get('catbox'), cached.get('telegraph')]) else None
                )
                
                await status_msg.delete()
                return
            
            # Create temp directory
            user_temp_dir = os.path.join(Config.TEMP_DIR, str(video_msg.from_user.id))
            os.makedirs(user_temp_dir, exist_ok=True)
            
            # Download video
            video_path = os.path.join(user_temp_dir, "video.mp4")
            
            last_update = [time.time()]
            last_pct = [-1]
            
            async def progress(current, total):
                pct = int((current / total) * 100) if total > 0 else 0
                if (pct - last_pct[0] >= 5) or (time.time() - last_update[0] >= 3):
                    await safe_edit(status_msg, ProgressBar.download(current, total))
                    last_update[0] = time.time()
                    last_pct[0] = pct
            
            await video_msg.download(file_name=video_path, progress=progress)
            
            # Extract screenshots
            await safe_edit(status_msg, "🎬 **Analyzing video...**")
            
            screenshots = await VideoProcessor.extract_screenshots(
                video_path, num_screenshots, quality, status_msg, safe_edit
            )
            
            if not screenshots:
                await safe_edit(status_msg, Messages.ERROR.format(
                    error="Failed to extract screenshots",
                    owner=Config.OWNER_USERNAME
                ))
                return
            
            screenshot_files = [s[0] for s in screenshots]
            
            # Create collage
            await safe_edit(status_msg, "🎨 **Creating cinematic collage...**")
            
            collage_path = os.path.join(user_temp_dir, "collage.jpg")
            success = CollageCreator.create_cinematic_collage(screenshots, collage_path)
            
            if not success:
                await safe_edit(status_msg, Messages.ERROR.format(
                    error="Collage creation failed",
                    owner=Config.OWNER_USERNAME
                ))
                return
            
            # Upload to cloud
            links = await CloudUploader.multi_upload(collage_path, status_msg, safe_edit)
            
            if not any(links.values()):
                # Send collage directly if upload fails
                await video_msg.reply_photo(
                    photo=collage_path,
                    caption=f"✅ **{filename}**\n\n📸 Screenshots: {len(screenshots)}\n🎨 Quality: {quality}\n\n_Upload failed, but here's your collage!_"
                )
                await status_msg.delete()
                return
            
            # Cache results
            db.cache_links(video_hash, links, len(screenshots), quality)
            
            # Update analytics
            file_size_mb = os.path.getsize(collage_path) / (1024 * 1024)
            process_time = int(time.time() - start_time)
            db.update_analytics(video_msg.from_user.id, len(screenshots), process_time, file_size_mb)
            
            # Format links
            links_text = MainProcessor._format_links(links)
            
            # Create keyboard
            keyboard_buttons = []
            if links.get('catbox'):
                keyboard_buttons.append([InlineKeyboardButton("🔗 Catbox", url=links['catbox'])])
            if links.get('telegraph'):
                keyboard_buttons.append([InlineKeyboardButton("🔗 Telegraph", url=links['telegraph'])])
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
            
            # Send collage as REPLY to original video
            await video_msg.reply_photo(
                photo=collage_path,
                caption=Messages.SUCCESS.format(
                    filename=filename,
                    count=len(screenshots),
                    size=f"{file_size_mb:.2f}",
                    duration=process_time,
                    quality=quality,
                    links=links_text
                ),
                reply_markup=keyboard
            )
            
            await status_msg.delete()
            
        except Exception as e:
            log.error(f"Processing error: {e}", exc_info=True)
            error_msg = str(e)
            if "timed out" in error_msg.lower():
                error_msg = "Download timeout. Try a smaller video."
            elif "no such file" in error_msg.lower():
                error_msg = "FFmpeg/FFprobe not found."
            
            await safe_edit(status_msg, Messages.ERROR.format(
                error=error_msg[:100],
                owner=Config.OWNER_USERNAME
            ))
        finally:
            # Cleanup
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
            
            if collage_path and os.path.exists(collage_path):
                try:
                    os.remove(collage_path)
                except:
                    pass
            
            for screenshot_file in screenshot_files:
                try:
                    if os.path.exists(screenshot_file):
                        os.remove(screenshot_file)
                except:
                    pass
    
    @staticmethod
    def _format_links(links: Dict) -> str:
        parts = []
        if links.get('catbox'):
            parts.append(f"🔗 [Catbox]({links['catbox']})")
        if links.get('telegraph'):
            parts.append(f"🔗 [Telegraph]({links['telegraph']})")
        return "\n".join(parts) if parts else "⚠️ No upload links available"

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
        if not db.is_owner(user.id, user.username):
            await message.reply_text(Messages.UNAUTHORIZED.format(owner=Config.OWNER_USERNAME))
            log.warning(f"Unauthorized: {user.username} ({user.id})")
            return
        return await func(client, message)
    return wrapper

# ═══════════════════════════════════════════════════════════════════
# SECTION 11: COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════

@app.on_message(filters.command("start"))
@authorized_only
async def start_command(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("⚙️ Quality", callback_data="quality")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats")
        ]
    ])
    await message.reply_text(Messages.START, reply_markup=keyboard)

@app.on_message(filters.command("help"))
@authorized_only
async def help_command(client: Client, message: Message):
    await message.reply_text(Messages.HELP)

@app.on_message(filters.command("stats"))
@authorized_only
async def stats_command(client: Client, message: Message):
    stats = db.get_user_stats(message.from_user.id)
    text = f"""
📊 **Your Statistics**

👤 User: @{message.from_user.username or 'User'}

━━━━━━━━━━━━━━━━

📸 Total Screenshots: {stats['screenshots']}
🎬 Videos Processed: {stats['videos']}
⏱️ Total Time: {stats['time']}s
💾 Storage Used: {stats['storage']:.2f} MB

━━━━━━━━━━━━━━━━
_Thank you for using @Linkz_Wallah!_
"""
    await message.reply_text(text)

@app.on_message(filters.command("quality"))
@authorized_only
async def quality_command(client: Client, message: Message):
    current = db.get_user_quality(message.from_user.id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅ ' if current == 'low' else ''}Low (640p)",
                callback_data="quality_low"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current == 'medium' else ''}Medium (960p)",
                callback_data="quality_medium"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅ ' if current == 'high' else ''}High (1280p)",
                callback_data="quality_high"
            )
        ]
    ])
    await message.reply_text(
        f"🎨 **Quality Settings**\n\nCurrent: **{current.title()}**\n\nChoose your preferred quality:",
        reply_markup=keyboard
    )

# ═══════════════════════════════════════════════════════════════════
# SECTION 12: VIDEO HANDLER
# ═══════════════════════════════════════════════════════════════════

@app.on_message(filters.video | filters.document)
@authorized_only
async def video_handler(client: Client, message: Message):
    try:
        video = message.video or message.document
        
        # Check if document is video
        if message.document and not message.document.mime_type.startswith('video/'):
            return
        
        # Size check
        if video.file_size > Config.MAX_VIDEO_SIZE:
            await message.reply_text(Messages.VIDEO_TOO_LARGE.format(
                size=f"{video.file_size / (1024*1024):.1f}"
            ))
            return
        
        # Duration check
        if hasattr(video, 'duration') and video.duration and video.duration > Config.MAX_DURATION:
            await message.reply_text(Messages.VIDEO_TOO_LONG.format(
                duration=f"{video.duration / 60:.1f}"
            ))
            return
        
        # Store video message
        user_videos[message.from_user.id] = message
        
        # Show screenshot count selection
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("4 Screenshots", callback_data="ss_4"),
                InlineKeyboardButton("6 Screenshots", callback_data="ss_6"),
            ],
            [
                InlineKeyboardButton("8 Screenshots", callback_data="ss_8"),
                InlineKeyboardButton("9 Screenshots", callback_data="ss_9"),
            ],
            [
                InlineKeyboardButton("10 Screenshots", callback_data="ss_10"),
                InlineKeyboardButton("12 Screenshots", callback_data="ss_12"),
            ],
            [
                InlineKeyboardButton("15 Screenshots", callback_data="ss_15"),
            ]
        ])
        
        await message.reply_text(
            "📸 **Select Screenshot Count**\n\nHow many screenshots do you want?",
            reply_markup=keyboard
        )
        
    except Exception as e:
        log.error(f"Video handler error: {e}")
        await message.reply_text(Messages.ERROR.format(
            error="Failed to process video request",
            owner=Config.OWNER_USERNAME
        ))

# ═══════════════════════════════════════════════════════════════════
# SECTION 13: CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════

@app.on_callback_query(filters.regex(r"^ss_\d+$"))
async def screenshot_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_videos:
        await callback.answer("❌ Please send a video first!", show_alert=True)
        return
    
    num = int(callback.data.split("_")[1])
    video_msg = user_videos[user_id]
    
    await callback.answer()
    
    # Add to queue
    position = await video_queue.add(video_msg, num, user_id)
    
    # Get filename
    video = video_msg.video or video_msg.document
    filename = getattr(video, 'file_name', 'video.mp4')
    
    # Calculate estimated wait time
    wait_time = f"{(position - 1) * 2} min" if position > 1 else "Starting now"
    
    # Send queue confirmation
    await callback.message.edit_text(
        Messages.QUEUE_ADDED.format(
            filename=filename,
            position=position,
            wait_time=wait_time
        )
    )

@app.on_callback_query(filters.regex(r"^quality_"))
async def quality_callback(client: Client, callback: CallbackQuery):
    quality = callback.data.split("_")[1]
    db.set_user_quality(callback.from_user.id, quality)
    await callback.answer(f"✅ Quality set to {quality.title()}", show_alert=True)
    
    # Update keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅ ' if quality == 'low' else ''}Low (640p)",
                callback_data="quality_low"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if quality == 'medium' else ''}Medium (960p)",
                callback_data="quality_medium"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅ ' if quality == 'high' else ''}High (1280p)",
                callback_data="quality_high"
            )
        ]
    ])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except:
        pass

@app.on_callback_query(filters.regex(r"^help$"))
async def help_callback(client: Client, callback: CallbackQuery):
    await callback.answer()
    await callback.message.reply_text(Messages.HELP)

@app.on_callback_query(filters.regex(r"^stats$"))
async def stats_callback(client: Client, callback: CallbackQuery):
    await callback.answer()
    stats = db.get_user_stats(callback.from_user.id)
    text = f"""
📊 **Your Statistics**

👤 User: @{callback.from_user.username or 'User'}

━━━━━━━━━━━━━━━━

📸 Total Screenshots: {stats['screenshots']}
🎬 Videos Processed: {stats['videos']}
⏱️ Total Time: {stats['time']}s
💾 Storage Used: {stats['storage']:.2f} MB

━━━━━━━━━━━━━━━━
"""
    await callback.message.reply_text(text)

# ═══════════════════════════════════════════════════════════════════
# SECTION 14: QUEUE PROCESSOR WORKER
# ═══════════════════════════════════════════════════════════════════

async def queue_processor():
    """Background worker to process video queue"""
    log.info("Queue processor started")
    
    while True:
        try:
            if not video_queue.is_empty():
                item = await video_queue.get_next()
                
                if item:
                    video_msg = item['video_msg']
                    num_screenshots = item['num_screenshots']
                    user_id = item['user_id']
                    filename = item['filename']
                    
                    log.info(f"Processing: {filename} for user {user_id}")
                    
                    # Create status message
                    status_msg = await video_msg.reply_text("⚙️ **Processing started...**")
                    
                    # Get current queue size
                    queue_total = video_queue.queue.qsize() + 1
                    queue_position = 1
                    
                    # Process the video
                    await MainProcessor.process_video(
                        status_msg,
                        video_msg,
                        num_screenshots,
                        queue_position,
                        queue_total
                    )
                    
                    # Mark as done
                    video_queue.task_done()
                    
                    log.info(f"Completed: {filename}")
            else:
                # Queue empty, wait
                await asyncio.sleep(2)
                
        except Exception as e:
            log.error(f"Queue processor error: {e}", exc_info=True)
            await asyncio.sleep(5)

# ═══════════════════════════════════════════════════════════════════
# SECTION 15: MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def main():
    log.info("=" * 60)
    log.info("LINKZ SCREENSHOT BOT - Starting...")
    log.info(f"Owner: @{Config.OWNER_USERNAME}")
    log.info("=" * 60)
    
    # Test FFmpeg
    log.info("Testing FFmpeg installation...")
    try:
        import subprocess
        
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            log.info(f"✅ FFmpeg: {version_line}")
        else:
            log.error("❌ FFmpeg test failed")
            
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            log.info(f"✅ FFprobe: {version_line}")
        else:
            log.error("❌ FFprobe test failed")
            
    except FileNotFoundError as e:
        log.error(f"❌ FFmpeg/FFprobe not found: {e}")
        log.error("   Make sure APT buildpack is installed!")
    except Exception as e:
        log.error(f"❌ Error testing FFmpeg: {e}")
    
    if MOVIEPY_AVAILABLE:
        log.info("✅ MoviePy available as fallback")
    else:
        log.info("ℹ️  MoviePy not installed (using FFmpeg)")
    
    await app.start()
    
    me = await app.get_me()
    log.info(f"✅ Bot started: @{me.username}")
    log.info("=" * 60)
    
    # Start queue processor in background
    queue_task = asyncio.create_task(queue_processor())
    log.info("✅ Queue processor started")
    
    try:
        await idle()
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    finally:
        queue_task.cancel()
        await app.stop()
        log.info("Bot stopped.")

if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        log.info("Bot interrupted")
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)

