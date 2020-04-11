import json

from download import Download
from flask import Flask, render_template, request
from os import path

CONFIG_FILE = "config.json"
CONFIG = {
    "download_directory": "downloads",
    "download_speed": 250,  # kB/s,
    "port": 5000
}

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

downloads = []


@app.route('/')
def main():
    return render_template('main_panel.html')


@app.route('/api/download/new', methods=["POST"])
def new_download():
    url = request.form.get('url', '').strip()
    category = request.form.get('category', '')
    cookies = json.loads(request.form.get('cookies', '{}'))

    if len(url) == 0:
        return 'bad request'

    download = Download(url,
                        path.join(CONFIG["download_directory"], category),
                        referer=request.form.get('referer'),
                        user_agent=request.form.get('userAgent'),
                        cookies=cookies)
    downloads.append(download)
    set_download_limit(CONFIG["download_speed"])
    download.start(asynch=True)
    return 'ok'


@app.route('/api/download/cancel', methods=["POST"])
def cancel_download():
    url = request.form.get('url', '').strip()
    if len(url) == 0:
        return 'bad request'
    download_to_remove = None
    for download in downloads:
        if download.url == url:
            download.cancel()
            download_to_remove = download
            break
    if download_to_remove is not None:
        downloads.remove(download_to_remove)
    return 'ok'


@app.route('/api/downloads')
def get_downloads():
    set_download_limit(CONFIG["download_speed"])

    return json.dumps({download.url: {
        'speed': download.speed,
        'fileSize': download.file_size,
        'fileName': download.file_name,
        'fileSizeDownloaded': download.downloaded_bytes,
        'percentage': download.percentage,
        'finished': download.finished
    } for download in downloads})


@app.route('/api/getLimit')
def get_download_limit():
    return str(CONFIG["download_speed"])


@app.route('/api/setLimit/<int:limit>')
def set_download_limit(limit):  # type: (int) -> str
    if limit is not None and limit == 0:
        limit = None

    if CONFIG["download_speed"] != limit:
        save_later = True
    else:
        save_later = False

    # noinspection PyTypeChecker
    CONFIG["download_speed"] = limit

    if save_later:
        save_config()

    running_downloads = [download for download in downloads if not download.finished]
    for download in running_downloads:
        download.download_speed_limit = limit * 1024 / len(running_downloads) if limit is not None else None
    return 'ok'


def load_config():
    if path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            CONFIG.update(json.load(f))


def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(CONFIG, f, indent=1)


if __name__ == '__main__':
    load_config()
    app.run(port=CONFIG['port'])
