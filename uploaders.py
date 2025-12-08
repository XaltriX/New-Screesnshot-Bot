# uploaders.py - Upload Functions with Failover
import httpx
import os
from config import CATBOX_API_ENDPOINT, ENVS_API_ENDPOINT, TELEGRAPH_API_ENDPOINT

async def upload_to_catbox(file_path):
    """Upload to Catbox.moe"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': f}
                data = {'reqtype': 'fileupload'}
                response = await client.post(CATBOX_API_ENDPOINT, files=files, data=data)
                
                if response.status_code == 200:
                    return response.text.strip()
    except Exception as e:
        print(f"Catbox upload error: {e}")
    return None

async def upload_to_envs(file_path):
    """Upload to Envs.sh"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = await client.post(ENVS_API_ENDPOINT, files=files)
                
                if response.status_code == 200:
                    return response.text.strip()
    except Exception as e:
        print(f"Envs.sh upload error: {e}")
    return None

async def upload_to_telegraph(file_path):
    """Upload to Telegraph"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': ('file', f, 'image/jpeg')}
                response = await client.post(TELEGRAPH_API_ENDPOINT, files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        return f"https://telegra.ph{data[0].get('src', '')}"
    except Exception as e:
        print(f"Telegraph upload error: {e}")
    return None

async def upload_to_telegram(file_path, client, chat_id):
    """Upload to Telegram as fallback"""
    try:
        msg = await client.send_document(chat_id, file_path)
        if msg.document:
            return f"Telegram File ID: {msg.document.file_id}"
    except Exception as e:
        print(f"Telegram upload error: {e}")
    return None

async def upload_with_failover(file_path, filename, client=None, chat_id=None):
    """Upload with automatic failover"""
    print(f"Starting upload for: {filename}")
    
    # Try Catbox
    print("Trying Catbox...")
    url = await upload_to_catbox(file_path)
    if url:
        print(f"Catbox success: {url}")
        return url
    
    # Try Envs.sh
    print("Trying Envs.sh...")
    url = await upload_to_envs(file_path)
    if url:
        print(f"Envs.sh success: {url}")
        return url
    
    # Try Telegraph
    print("Trying Telegraph...")
    url = await upload_to_telegraph(file_path)
    if url:
        print(f"Telegraph success: {url}")
        return url
    
    # Fallback to Telegram
    if client and chat_id:
        print("Trying Telegram...")
        url = await upload_to_telegram(file_path, client, chat_id)
        if url:
            print(f"Telegram success: {url}")
            return url
    
    print("All upload methods failed!")
    return "Upload failed"
