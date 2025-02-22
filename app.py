from flask import Flask, render_template, request, send_file
from yt_dlp import YoutubeDL
import instaloader
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json  # Add this import

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def get_youtube_cookies():
    # Set up Selenium with ChromeDriver
    service = Service(executable_path='chromedriver.exe')  # Path to ChromeDriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--disable-gpu')  # Disable GPU for headless mode
    options.add_argument('--no-sandbox')  # Disable sandbox for headless mode
    options.add_argument('--disable-dev-shm-usage')  # Disable shared memory usage
    options.add_argument('--disable-extensions')  # Disable extensions
    options.add_argument('--disable-logging')  # Disable logging
    options.add_argument('--disable-blink-features=AutomationControlled')  # Disable automation detection
    driver = webdriver.Chrome(service=service, options=options)

    # Log in to YouTube
    driver.get('https://www.youtube.com')

    # Wait for a specific element to appear (e.g., the YouTube logo)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, 'logo-icon-container')))
    except:
        print("Element not found, but proceeding anyway.")

    # Extract cookies
    cookies = driver.get_cookies()
    driver.quit()

    # Format cookies for yt-dlp
    cookie_dict = {}
    for cookie in cookies:
        cookie_dict[cookie['name']] = cookie['value']
    return cookie_dict

def download_youtube_video(url):
    # Get cookies using Selenium
    cookies = get_youtube_cookies()
    ydl_opts = {
        'format': 'best[ext=mp4]',  # Download the best single-stream MP4 video
        'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save the video with its title as the filename
        'cookiefile': None,  # Disable cookiefile
        'cookiejar': cookies,  # Pass the extracted cookies
        'socket_timeout': 10,  # Set a timeout for network requests
        'noprogress': True,  # Disable progress updates to speed up the process
        'quiet': True,  # Suppress output to reduce overhead
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info_dict)  # Return the actual filename

@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    platform = request.form['platform']

    if platform == 'youtube':
        try:
            filename = download_youtube_video(url)
            return send_file(filename, as_attachment=True)
        except Exception as e:
            return str(e)

    elif platform == 'instagram':
        try:
            # Load Instagram cookies from the JSON file
            with open('instagram_cookies.json', 'r') as f:
                cookies = json.load(f)

            # Initialize instaloader
            L = instaloader.Instaloader()

            # Manually set the cookies in instaloader
            for cookie in cookies:
                L.context._session.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=cookie['domain'],
                    path=cookie['path'],
                    secure=cookie['secure'],
                    expires=cookie.get('expirationDate')
                )

            # Download the Instagram post
            post = instaloader.Post.from_shortcode(L.context, url.split('/')[-2])
            L.download_post(post, target='downloads')
            return send_file(f'downloads/{post.date_utc.strftime("%Y-%m-%d_%H-%M-%S")}_UTC.mp4', as_attachment=True)
        except Exception as e:
            return str(e)

    return "Unsupported platform"

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)