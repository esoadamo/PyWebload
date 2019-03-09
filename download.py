import requests
import re
import json
import time

from os import path, makedirs
from threading import Thread


class Download:
    def __init__(self, url, target_folder):
        self.url = url
        self.target_folder = target_folder
        self.target_file = None
        self.file_name = None
        self.file_size = 0
        self.download_speed_limit = None
        self.finished = False
        self.downloaded_bytes = 0
        self.speed = 0
        self.percentage = 0
        self.time_start = 0

    def start(self, asynch=False):
        class ThreadDownload(Thread):
            # noinspection PyMethodParameters
            def run(__):
                r = requests.get(self.url, stream=True)
                self.file_size = r.headers.get('Content-Length', None)
                if self.file_size is not None:
                    self.file_size = int(self.file_size)
                self.file_name = None
                if 'Content-Disposition' in r.headers:
                    re_filename = re.search('filename="(.*)"', r.headers['Content-Disposition'], re.I | re.M)
                    if re_filename:
                        self.file_name = re_filename.groups()[0]
                if self.file_name is None:
                    self.file_name = path.basename(self.url)
                    if '?' in self.file_name:
                        self.file_name = self.file_name[:self.file_name.index('?')]
                    if '.' not in self.file_name:
                        self.file_name = self.file_name[::-1].replace('-', '.', 1)[::-1]
                self.target_file = path.join(self.target_folder, self.file_name)
                self.time_start = time.time()
                self.downloaded_bytes = 0
                self.percentage = 0
                self.finished = False
                if not path.exists(self.target_folder):
                    makedirs(self.target_folder)
                with open(self.target_file, 'wb') as f:
                    chunk_start = time.time()
                    chunk_size = 8192
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
                        if self.download_speed_limit is not None:
                            sleep_for = chunk_start + (chunk_size / self.download_speed_limit) - time.time()
                            if sleep_for > 0:
                                time.sleep(sleep_for)
                        self.downloaded_bytes += chunk_size
                        self.percentage = 100 * self.downloaded_bytes / self.file_size
                        time_taken = time.time() - chunk_start
                        if time_taken == 0:
                            self.speed = chunk_size
                        else:
                            self.speed = chunk_size / time_taken
                        chunk_start = time.time()

                r.close()
                self.finished = True
        thread = ThreadDownload()
        thread.start()
        if not asynch:
            thread.join()


if __name__ == '__main__':
    d = Download('http://server/owncloud/index.php/s/tBBSLcRFX9nKjd9/download', r'c:\tmp')
    d.download_speed_limit = None
    d.start(True)
    while True:
        print(d.speed / 1024, d.percentage)
        time.sleep(1)
