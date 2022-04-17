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
        self.download_speed_limit: Optional[int] = None

        self.__url: str = url
        self.__dir_target: Path = dir_target if dir_target is not None else Path.cwd()
        self.__file_target: Optional[Path] = None
        self.__file_chunks: Optional[Path] = None
        self.__target_size: Optional[int] = None
        self.__finished: bool = False
        self.__downloaded_bytes: int = 0
        self.__speed: float = 0
        self.__time_start: int = 0
        self.__cookies: Optional[Dict[str, str]] = cookies
        self.__headers: Dict[str, str] = {}
        self.__cancel = False

        if referer is not None:
            self.__headers['Referer'] = referer
        if user_agent is not None:
            self.__headers['User-Agent'] = user_agent

    @property
    def url(self) -> str:
        return self.__url

    @property
    def dir_target(self) -> Path:
        return self.__dir_target

    @property
    def file_target(self) -> Optional[Path]:
        return self.__file_target

    @property
    def file_chunks(self) -> Optional[Path]:
        return self.__file_chunks

    @property
    def target_size(self) -> int:
        return self.__target_size

    @property
    def downloaded_bytes(self) -> int:
        return self.__downloaded_bytes

    @property
    def speed(self) -> float:
        return self.__speed

    @property
    def percentage(self) -> float:
        if self.__target_size is None or self.__target_size == 0:
            return 0.0
        return 100 * self.__downloaded_bytes / self.__target_size

    @property
    def time_start(self) -> float:
        return self.__time_start

    @property
    def cookies(self) -> Optional[Dict[str, str]]:
        return dict(self.__cookies) if self.__cookies is not None else None

    @property
    def headers(self) -> Dict[str, str]:
        return dict(self.__headers)

    @property
    def finished(self) -> bool:
        return self.__finished

    @property
    def canceled(self) -> bool:
        return self.__cancel

    def start(self, wait_for_completion: bool = True, retry_count: int = 0, retry_sleep_time: float = 10) -> None:
        thread = Thread(target=self.start_sync, args=(retry_count, retry_sleep_time))
        thread.start()
        if wait_for_completion:
            thread.join()

    def start_sync(self, retry_count: int = 0, retry_sleep_time: float = 10) -> None:
        self.__dir_target.mkdir(parents=True, exist_ok=True)
        self.__downloaded_bytes = 0
        self.__finished = False
        file_name: Optional[str] = None

        for ch_file in self.dir_target.iterdir():
            if re.match(rf"^.*{re.escape(self.__file_chunk_suffix)}$", ch_file.name):
                file_name = ch_file.name[:-len(self.__file_chunk_suffix)]
                self.__file_chunks = ch_file
                self.__headers["Range"] = f"bytes={ch_file.stat().st_size}-"

        try:
            req = requests.get(self.__url, stream=True, headers=self.__headers, cookies=self.__cookies)
            self.__target_size = req.headers.get('Content-Length', None)
            if self.__target_size is not None:
                self.__target_size = int(self.__target_size)

            if file_name is None and 'Content-Disposition' in req.headers:
                re_filename = re.search('filename="(.*)"', req.headers['Content-Disposition'], re.I | re.M)
                if re_filename:
                    file_name = re_filename.groups()[0]
            if file_name is None:
                file_name = Path(self.__url).name
                if '?' in file_name:
                    file_name = file_name[:file_name.index('?')]
                if '#' in file_name:
                    file_name = file_name[:file_name.index('?')]
                if '.' not in file_name:
                    file_name = file_name[::-1].replace('-', '.', 1)[::-1]

            self.__file_target = self.__dir_target.joinpath(Path(file_name).name).resolve()
            del file_name
            if self.__file_chunks is None:
                self.__file_chunks = self.__dir_target.joinpath(
                    self.__file_target.name + self.__file_chunk_suffix
                )
            self.__time_start = time.time()

            with self.__file_chunks.open('ab' if req.status_code == 206 else 'wb') as f:
                already_downloaded_bytes = self.file_chunks.stat().st_size
                self.__downloaded_bytes = already_downloaded_bytes
                self.__target_size += already_downloaded_bytes
                del already_downloaded_bytes

                while not self.__cancel:
                    if self.download_speed_limit:
                        max_data_per_2_ms = int(max(1, self.download_speed_limit * 2 // 100))
                    else:
                        max_data_per_2_ms = 8192
                    time_chunk_start = time.time()
                    try:
                        data = next(req.iter_content(chunk_size=max_data_per_2_ms))
                    except StopIteration:
                        break
                    if self.download_speed_limit:
                        while time.time() - time_chunk_start < 0.02:
                            time.sleep(0.005)
                    time_chunk_end = time.time()
                    f.write(data)
                    self.__speed = len(data) / (time_chunk_end - time_chunk_start)
                    self.__downloaded_bytes += len(data)

            req.close()
        except requests.exceptions.ConnectionError:
            if retry_count > 0:
                time.sleep(retry_sleep_time)
                self.start_sync(retry_count=retry_count - 1, retry_sleep_time=retry_sleep_time * 2)
                return
            else:
                self.cancel()
        if not self.__cancel:
            move(self.__file_chunks, self.__file_target)
        else:
            self.__file_chunks.unlink(missing_ok=True)
        self.__finished = True

    def cancel(self):
        self.__cancel = True

    @property
    def __file_chunk_suffix(self) -> str:
        return '.' + md5(self.__url.encode('utf8')).hexdigest() + '.chunk'


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
                print(f"\rspeed={d.speed / 1024:04.2f} KiBps, percentage={d.percentage:03.1f} %", end="", flush=True)
                time.sleep(1)
            print()
            return 0
        except KeyboardInterrupt:
            d.cancel()
            return 2

    exit(main())
