from flask import Flask, render_template, request, send_file
from yt_dlp import YoutubeDL
import instaloader
import os
import json
import re
import subprocess
from functools import lru_cache

app = Flask(__name__)

# Configuration
FFMPEG_PATH = r'C:\Users\UniC\OneDrive\Desktop\social-media-downloader\ffmpeg\bin\ffmpeg.exe'
FFPROBE_PATH = r'C:\Users\UniC\OneDrive\Desktop\social-media-downloader\ffmpeg\bin\ffprobe.exe'
DEFAULT_DIR = 'downloads'

def sanitize_filename(filename):
    """Clean filenames for Windows"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip('. ')

def get_video_height(path):
    """Get video height using ffprobe"""
    try:
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=height',
            '-of', 'csv=p=0', path
        ], capture_output=True, text=True)
        return int(result.stdout.strip()) if result.stdout else 0
    except Exception as e:
        print(f'FFprobe Error: {str(e)}')
        return 0

def convert_video(input_path, output_path, target_bitrate, force_landscape=False):
    """Convert video to target bitrate and optionally force 1280x720 resolution"""
    try:
        print(f"Starting conversion: {input_path} -> {output_path} with bitrate {target_bitrate}")
        if force_landscape:
            # Force 1280x720 resolution (for YouTube)
            subprocess.run([
                FFMPEG_PATH, '-i', input_path,
                '-vf', 'scale=1280:720',  # Force 1280x720 resolution
                '-b:v', target_bitrate,   # Set video bitrate
                '-preset', 'ultrafast',   # Use ultrafast encoding preset
                '-c:a', 'copy', '-y', output_path
            ], check=True, capture_output=True)
        else:
            # Preserve original resolution (for Instagram)
            subprocess.run([
                FFMPEG_PATH, '-i', input_path,
                '-b:v', target_bitrate,  # Set video bitrate
                '-preset', 'ultrafast',  # Use ultrafast encoding preset
                '-c:a', 'copy', '-y', output_path
            ], check=True, capture_output=True)
        print(f"Conversion successful: {output_path}")
        os.remove(input_path)  # Remove original file after conversion
        return output_path
    except subprocess.CalledProcessError as e:
        print(f'Conversion failed: {e.stderr.decode()}')
        return input_path

@lru_cache(maxsize=100)
def get_yt_info(url):
    """Get YouTube video info with error handling"""
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': sanitize_filename(info.get('title', 'video')),
                'formats': sorted(
                    (f for f in info.get('formats', []) if f.get('height')),
                    key=lambda x: x['height'], 
                    reverse=True
                )
            }
    except Exception as e:
        print(f'YouTube Info Error: {str(e)}')
        return {'title': 'video', 'formats': []}

def download_youtube(url, quality, output_dir):
    """Download YouTube video in the requested resolution"""
    os.makedirs(output_dir, exist_ok=True)
    video_info = get_yt_info(url)
    formats = video_info['formats']
    title = video_info['title']
    
    if not formats:
        print("No available formats found")
        return None

    # Debug: Print available formats
    print("Available YouTube Formats:")
    for f in formats:
        print(f"Format ID: {f['format_id']}, Resolution: {f.get('height', 'N/A')}, Ext: {f['ext']}")

    # Map quality to target resolution
    resolution_map = {
        'best': None,  # Best available quality
        '1080p': 1080,
        '720p': 720,
        '480p': 480,
    }
    target_resolution = resolution_map.get(quality, None)

    # Select the best format based on the requested quality
    if quality == 'best':
        # Download the best available format
        ydl_opts = {
            'outtmpl': f'{output_dir}/{title}.%(ext)s',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'noprogress': True,
            'n_threads': 20,  # Increase threads for faster downloads
        }
    else:
        # Download the closest available resolution to the target resolution
        ydl_opts = {
            'outtmpl': f'{output_dir}/{title}.%(ext)s',
            'format': f'bestvideo[height<={target_resolution}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'noprogress': True,
            'n_threads': 20,  # Increase threads for faster downloads
        }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)  # Ensure download=True
            original_path = ydl.prepare_filename(info)
            print(f"Downloaded video to: {original_path}")
            
            if quality == 'best':
                # Skip conversion for "Best" quality
                output_path = f'{output_dir}/{title}_{quality}.mp4'
                os.rename(original_path, output_path)
                print(f"Renamed file to: {output_path}")
                return output_path

            # Adjust bitrate based on selected quality
            bitrate_map = {
                '1080p': '4000k',  # Near-HD quality
                '720p': '2500k',   # Standard quality
                '480p': '1000k',   # Low quality
            }
            target_bitrate = bitrate_map.get(quality, '2500k')

            # Convert to the target resolution with target bitrate
            output_path = f'{output_dir}/{title}_{quality}.mp4'
            print(f"Converting video to: {output_path}")
            return convert_video(original_path, output_path, target_bitrate, force_landscape=True)
    except Exception as e:
        print(f'YouTube Download Error: {str(e)}')
        return None

def download_instagram(url, quality, output_dir):
    """Download Instagram video and preserve original vertical format"""
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Load Instagram cookies if available
        if os.path.exists('instagram_cookies.json'):
            with open('instagram_cookies.json') as f:
                cookies = json.load(f)
        else:
            cookies = None
        
        L = instaloader.Instaloader()
        
        if cookies:
            for cookie in cookies:
                L.context._session.cookies.set(
                    cookie['name'], cookie['value'],
                    domain=cookie['domain'], path=cookie['path'],
                    secure=cookie['secure'], expires=cookie.get('expirationDate')
                )

        # Extract shortcode from URL
        shortcode = url.split('/')[-2]
        if not shortcode:
            raise ValueError("Invalid Instagram URL. Could not extract shortcode.")
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=output_dir)
        
        base_name = post.date_utc.strftime("%Y-%m-%d_%H-%M-%S_UTC")
        original_path = f'{output_dir}/{base_name}.mp4'
        
        if not os.path.exists(original_path):
            raise FileNotFoundError(f"Downloaded file not found: {original_path}")
        
        if quality == 'best':
            # Skip conversion for "Best" quality
            return original_path

        # Map quality to target bitrate
        bitrate_map = {
            '1080p': '4000k',  # Near-HD quality
            '720p': '2500k',   # Standard quality
            '480p': '1000k',   # Low quality
        }
        target_bitrate = bitrate_map.get(quality, '2500k')

        output_path = f'{output_dir}/{base_name}_{quality}.mp4'
        return convert_video(original_path, output_path, target_bitrate, force_landscape=False)
        
    except Exception as e:
        print(f'Instagram Error: {str(e)}')
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def handle_download():
    data = request.form
    url = data['url']
    platform = data['platform']
    quality = data.get('quality', 'best')
    output_dir = data.get('output_dir', DEFAULT_DIR)

    try:
        if platform == 'youtube':
            file_path = download_youtube(url, quality, output_dir)
        elif platform == 'instagram':
            file_path = download_instagram(url, quality, output_dir)
        else:
            return "Unsupported platform", 400

        if file_path and os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        return "Download failed: Check server logs for details", 500
        
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    os.makedirs(DEFAULT_DIR, exist_ok=True)
    app.run(debug=True)