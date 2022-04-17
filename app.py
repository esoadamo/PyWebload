import json
from typing import List, TypedDict, Optional
from flask import Flask, render_template, request
from flask_cors import CORS, cross_origin
from pathlib import Path

from download import Download


class PyloadConfig(TypedDict):
    download_directory: str
    download_speed: Optional[int]
    port: int


FILE_CONFIG = Path("config.json")
CONFIG: PyloadConfig = {
    "download_directory": "downloads",
    "download_speed": 250,  # kB/s,
    "port": 5000
}

APP = Flask(__name__)
CORS(APP)

RUNNING_DOWNLOADS: List[Download] = []


@APP.route('/')
def main():
    return render_template('main_panel.html')


@APP.route('/api/download/new', methods=["POST"])
@cross_origin()
def new_download():
    url = request.form.get('url', '').strip()
    category = request.form.get('category', '')
    cookies = json.loads(request.form.get('cookies', '{}'))

    if len(url) == 0:
        return 'bad request', 400

    download = Download(url,
                        Path(CONFIG["download_directory"]).joinpath(Path(category).name).resolve(),
                        referer=request.form.get('referer'),
                        user_agent=request.form.get('userAgent'),
                        cookies=cookies)
    RUNNING_DOWNLOADS.append(download)
    set_download_limit(CONFIG["download_speed"])
    download.start(wait_for_completion=False)
    return 'ok'


@APP.route('/api/download/cancel', methods=["POST"])
def cancel_download():
    url = request.form.get('url', '').strip()
    if len(url) == 0:
        return 'bad request'
    download_to_remove = None
    for download in RUNNING_DOWNLOADS:
        if download.url == url:
            download.cancel()
            download_to_remove = download
            break
    if download_to_remove is not None:
        RUNNING_DOWNLOADS.remove(download_to_remove)
    return 'ok'


@APP.route('/api/downloads')
def get_downloads():
    set_download_limit(CONFIG["download_speed"])

    return json.dumps({download.url: {
        'speed': download.speed,
        'fileSize': download.target_size,
        'fileName': download.file_target.name,
        'fileSizeDownloaded': download.downloaded_bytes,
        'percentage': download.percentage,
        'finished': download.finished
    } for download in RUNNING_DOWNLOADS})


@APP.route('/api/getLimit')
def get_download_limit():
    return str(CONFIG["download_speed"])


@APP.route('/api/setLimit/<int:limit>')
def set_download_limit(limit):  # type: (int) -> str
    if limit is not None and limit == 0:
        limit = None

    if CONFIG["download_speed"] != limit:
        save_later = True
    else:
        save_later = False

    CONFIG["download_speed"] = limit

    if save_later:
        save_config()

    running_downloads = [download for download in RUNNING_DOWNLOADS if not download.finished]
    for download in running_downloads:
        download.download_speed_limit = limit * 1024 / len(running_downloads) if limit is not None else None
    return 'ok'


@APP.route('/api/ping', methods=['GET', 'POST'])
@cross_origin()
def api_ping():
    return 'pong'


def load_config() -> None:
    if FILE_CONFIG.exists():
        with FILE_CONFIG.open('r') as f:
            CONFIG.update(json.load(f))


def save_config():
    with FILE_CONFIG.open('w') as f:
        json.dump(CONFIG, f, indent=1)


if __name__ == '__main__':
    load_config()
    APP.run(port=CONFIG['port'])
