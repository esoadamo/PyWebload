import json

from download import Download
from flask import Flask, render_template, request
from os import path

DOWNLOAD_FOLDER = "e:\\tmp\\"

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

downloads = []
downloads_limit = [500000]


@app.route('/')
def main():
    return render_template('main_panel.html')


@app.route('/api/download', methods=["POST"])
def new_download():
    url = request.form.get('url', '').strip()
    category = request.form.get('category', '')
    if len(url) == 0:
        return 'bad request'
    download = Download(url, path.join(DOWNLOAD_FOLDER, category))
    downloads.append(download)
    set_download_limit(downloads_limit[0])
    download.start(asynch=True)
    return 'ok'


@app.route('/api/downloads')
def get_downloads():
    [downloads.remove(download) for download in [download for download in downloads if download.finished]]
    set_download_limit(downloads_limit[0])

    return json.dumps({download.url: {
        'speed': download.speed,
        'fileSize': download.file_size,
        'fileName': download.file_name,
        'fileSizeDownloaded': download.downloaded_bytes,
        'percentage': download.percentage
    } for download in downloads})


@app.route('/api/getLimit')
def get_download_limit():
    return str(downloads_limit[0])


@app.route('/api/setLimit/<int:limit>')
def set_download_limit(limit):
    if limit is not None and limit == 0:
        limit = None
    # noinspection PyTypeChecker
    downloads_limit[0] = limit
    for download in downloads:
        download.download_speed_limit = limit * 1024 / len(downloads) if limit is not None else None
    return 'ok'


if __name__ == '__main__':
    app.run()
