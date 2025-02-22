from flask import Flask, render_template, request, send_file
from yt_dlp import YoutubeDL
import instaloader
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def download_youtube_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]',  # Download the best single-stream MP4 video
        'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save the video with its title as the filename
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],  # Skip DASH and HLS formats
            },
        },
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
            L = instaloader.Instaloader()
            # Load session cookies for Instagram authentication
            L.load_session_from_file('your_instagram_username', 'cookies.txt')
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