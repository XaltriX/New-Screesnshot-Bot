# utils.py - Utility Functions
import os
import asyncio
import subprocess
import zipfile
from PIL import Image, ImageDraw, ImageFont
from config import COLLAGE_SIZE, DEFAULT_QUALITY, TEMP_DIR, OWNER_USERNAME, WATERMARK_TEXT

def create_user_temp_dir(user_id):
    """Create temporary directory for user"""
    path = os.path.join(TEMP_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def cleanup_user_temp(user_id):
    """Cleanup user's temporary files"""
    import shutil
    path = os.path.join(TEMP_DIR, str(user_id))
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"Cleanup error: {e}")

async def get_video_duration(video_path):
    """Get video duration using ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        print(f"Running ffprobe: {' '.join(cmd)}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if stderr:
            print(f"FFprobe stderr: {stderr.decode()}")
        
        duration = float(stdout.decode().strip())
        print(f"Video duration: {duration}s")
        return duration
        
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0

async def generate_screenshots_with_watermark(video_path, output_dir, duration, count, watermark_text):
    """Generate screenshots WITHOUT FFmpeg watermark (add later with PIL)"""
    print(f"Generating {count} screenshots from {duration}s video...")
    
    interval = duration / (count + 1)
    screenshots = []
    
    # Generate screenshots WITHOUT watermark first
    for i in range(1, count + 1):
        timestamp = interval * i
        output_file = os.path.join(output_dir, f"shot_{i:03d}.jpg")
        
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            output_file
        ]
        
        print(f"Generating screenshot {i}/{count} at {timestamp:.2f}s...")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0 and os.path.exists(output_file):
                # Add watermark using PIL
                try:
                    img = Image.open(output_file)
                    draw = ImageDraw.Draw(img)
                    
                    # Try to load font
                    try:
                        font = ImageFont.truetype("arial.ttf", 40)
                    except:
                        font = ImageFont.load_default()
                    
                    # Get image size
                    width, height = img.size
                    
                    # Get text size
                    bbox = draw.textbbox((0, 0), watermark_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Position at bottom right
                    x = width - text_width - 20
                    y = height - text_height - 20
                    
                    # Draw background box
                    padding = 5
                    draw.rectangle(
                        [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
                        fill=(0, 0, 0, 128)
                    )
                    
                    # Draw text
                    draw.text((x, y), watermark_text, fill='white', font=font)
                    
                    # Save
                    img.save(output_file, quality=90)
                    
                    screenshots.append(output_file)
                    print(f"✓ Screenshot {i} created with watermark")
                    
                except Exception as e:
                    print(f"Watermark error on {i}, keeping without watermark: {e}")
                    screenshots.append(output_file)
                    
            else:
                print(f"✗ Screenshot {i} failed")
                if stderr:
                    error_msg = stderr.decode()
                    print(f"FFmpeg error: {error_msg[-500:]}")
                    
        except Exception as e:
            print(f"Error creating screenshot {i}: {e}")
    
    print(f"Total screenshots created: {len(screenshots)}")
    return screenshots
    
    print(f"Total screenshots created: {len(screenshots)}")
    return screenshots
    
    print(f"Total screenshots created: {len(screenshots)}")
    return screenshots

async def create_collage(screenshot_files, output_path, owner_username):
    """Create cinematic collage grid"""
    print(f"Creating collage with {len(screenshot_files)} images...")
    
    count = len(screenshot_files)
    
    # Determine grid layout
    if count <= 4:
        rows, cols = 2, 2
    elif count <= 6:
        rows, cols = 2, 3
    else:
        rows, cols = 2, 5
    
    print(f"Grid layout: {rows}x{cols}")
    
    # Create canvas
    canvas = Image.new('RGB', COLLAGE_SIZE, color='black')
    draw = ImageDraw.Draw(canvas)
    
    # Calculate cell dimensions
    cell_width = COLLAGE_SIZE[0] // cols
    cell_height = (COLLAGE_SIZE[1] - 60) // rows  # Leave space for bottom text
    
    # Paste screenshots
    for idx, screenshot_path in enumerate(screenshot_files):
        if idx >= rows * cols:
            break
        
        row = idx // cols
        col = idx % cols
        
        try:
            img = Image.open(screenshot_path)
            img = img.resize((cell_width, cell_height), Image.LANCZOS)
            
            x = col * cell_width
            y = row * cell_height
            
            canvas.paste(img, (x, y))
            print(f"✓ Pasted image {idx + 1} at ({x}, {y})")
            
        except Exception as e:
            print(f"Error pasting image {idx + 1}: {e}")
    
    # Add bottom watermark
    try:
        # Try to load a nice font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except:
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 30)
            except:
                font = ImageFont.load_default()
        
        watermark_text = f"Processed by @{owner_username}"
        
        # Get text size
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (COLLAGE_SIZE[0] - text_width) // 2
        text_y = COLLAGE_SIZE[1] - 50
        
        draw.text((text_x, text_y), watermark_text, fill='white', font=font)
        print("✓ Added watermark")
        
    except Exception as e:
        print(f"Error adding watermark: {e}")
    
    canvas.save(output_path, quality=DEFAULT_QUALITY)
    print(f"✓ Collage saved: {output_path}")

async def create_zip_archive(files, output_path):
    """Create ZIP archive of screenshots"""
    print(f"Creating ZIP with {len(files)} files...")
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                zipf.write(file, os.path.basename(file))
        
        print(f"✓ ZIP created: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating ZIP: {e}")
        return False

def format_progress_bar(current, total, length=10):
    """Format progress bar with hearts"""
    if total == 0:
        return "♥" * length + " 0%"
    
    percent = current / total
    filled = int(length * percent)
    bar = '♥' * filled + '♡' * (length - filled)
    return f"{bar} {int(percent * 100)}%"
