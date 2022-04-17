import requests
import re
import time

from threading import Thread
from shutil import move
from typing import Optional, Dict
from pathlib import Path
from hashlib import md5


class Download:
    def __init__(self,
                 url: str,
                 dir_target: Optional[Path] = None,
                 cookies: Optional[Dict[str, str]] = None,
                 referer: str = None,
                 user_agent: str = None
                 ):
        self.url: str = url
        self.dir_target: Optional[Path] = dir_target
        self.file_target: Optional[Path] = None
        self.file_chunks: Optional[Path] = None
        self.file_size: int = 0
        self.download_speed_limit: Optional[int] = None
        self.finished: bool = False
        self.downloaded_bytes: int = 0
        self.speed: float = 0
        self.percentage: float = 0
        self.time_start: int = 0
        self.cookies: Optional[Dict[str, str]] = cookies
        self.headers: Optional[Dict[str, str]] = {}

        if self.dir_target is None:
            self.dir_target = Path.cwd()
        if referer is not None:
            self.headers['Referer'] = referer
        if user_agent is not None:
            self.headers['User-Agent'] = user_agent

        self._cancel = False

    def start(self, wait_for_completion: bool = True) -> None:
        thread = Thread(target=self.start_sync)
        thread.start()
        if wait_for_completion:
            thread.join()

    def start_sync(self) -> None:
        self.dir_target.mkdir(parents=True, exist_ok=True)
        self.downloaded_bytes = 0
        self.percentage = 0
        self.finished = False

        try:
            req = requests.get(self.url, stream=True, headers=self.headers, cookies=self.cookies)
            self.file_size = req.headers.get('Content-Length', None)
            if self.file_size is not None:
                self.file_size = int(self.file_size)

            file_name: Optional[str] = None
            if 'Content-Disposition' in req.headers:
                re_filename = re.search('filename="(.*)"', req.headers['Content-Disposition'], re.I | re.M)
                if re_filename:
                    file_name = re_filename.groups()[0]
            if file_name is None:
                file_name = Path(self.url).name
                if '?' in file_name:
                    file_name = file_name[:file_name.index('?')]
                if '#' in file_name:
                    file_name = file_name[:file_name.index('?')]
                if '.' not in file_name:
                    file_name = file_name[::-1].replace('-', '.', 1)[::-1]

            self.file_target = self.dir_target.joinpath(Path(file_name).name).resolve()
            del file_name
            self.file_chunks = self.dir_target.joinpath(
                self.file_target.name + md5(self.url.encode('utf8')).hexdigest() + '.chunk'
            )
            self.time_start = time.time()

            with open(self.file_chunks, 'wb') as f:
                chunk_start = time.time()
                speed_counting_start = time.time()
                speed_counting_bytes = 0
                chunk_size = 8192
                for chunk in req.iter_content(chunk_size=chunk_size):
                    if self._cancel:
                        break
                    f.write(chunk)
                    if self.download_speed_limit is not None:
                        sleep_for = chunk_start + (chunk_size / self.download_speed_limit) - time.time()
                        if sleep_for > 0:
                            time.sleep(sleep_for)
                    self.downloaded_bytes += chunk_size
                    self.percentage = 100 * self.downloaded_bytes / self.file_size
                    time_taken = time.time() - speed_counting_start
                    speed_counting_bytes += chunk_size
                    if time_taken >= 1:
                        self.speed = speed_counting_bytes / time_taken
                        speed_counting_bytes = 0
                        speed_counting_start = time.time()
                    chunk_start = time.time()
            req.close()
        except requests.exceptions.ConnectionError:
            self.cancel()
        if not self._cancel:
            move(self.file_chunks, self.file_target)
        else:
            self.file_chunks.unlink(missing_ok=True)
        self.finished = True

    def cancel(self):
        self._cancel = True


if __name__ == '__main__':
    def main() -> int:
        from sys import argv
        try:
            d = Download(argv[1])
            d.download_speed_limit = int(argv[2]) * 1024
        except (IndexError, ValueError):
            print(f'Usage: {argv[0]} url speed_KiBps')
            return 1
        d.start(wait_for_completion=False)
        try:
            while not d.finished:
                print(f"\rspeed={d.speed / 1024:04.2f} KiBps, percentage={d.percentage:03.1f}%", end="", flush=True)
                time.sleep(1)
            return 0
        except KeyboardInterrupt:
            d.cancel()
            return 2

    exit(main())
