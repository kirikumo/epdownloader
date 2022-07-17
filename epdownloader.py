import argparse
import json
import logging
import multiprocessing
import os
import random
import re
import signal
import subprocess
import sys
import time
from datetime import datetime as dat
from pathlib import Path
import traceback
from urllib.request import Request, urlopen

from aiom3u8downloader.aiodownloadm3u8 import AioM3u8Downloader
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from config import (
    HIGH_QUALITY_HOST,
    HIS_FILE_PATH,
    LIMIT_GET_PAGE_VIDEO,
    SUBSCRIPTION_URL_LIST,
    USER_AGENTS,
)
from .notify_hook import NotifyHook


class CustomFormatter(logging.Formatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    blue = '\033[34m'
    green = '\033[32m'
    red = '\033[31m'
    yellow = '\033[33m'
    on_red = '\033[41m'

    # grey = '\x1b[38;21m'
    bold_red = '\x1b[31;1m'
    reset = '\033[0m'

    fmt = ' %(message)s'
    baseFormat = \
        '[%(asctime)s: %(levelname)s] [%(filename)s:%(lineno)d]'

    FORMATS = {
        logging.DEBUG: baseFormat + fmt,
        logging.INFO: baseFormat + fmt,
        logging.WARNING: baseFormat + fmt,
        logging.ERROR: baseFormat + fmt,
        logging.FATAL: baseFormat + fmt,
        logging.CRITICAL: baseFormat + fmt
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def getLogger(filePath=None, level=logging.INFO):
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logFormat = CustomFormatter()

    if filePath is not None:
        os.makedirs(os.path.dirname(filePath), exist_ok=True)
        fh = logging.FileHandler(filePath)
        fh.setFormatter(logFormat)
        logger.addHandler(fh)

    return logger


logger = logging.getLogger()


def signal_handler(sig, frame):
    sys.exit(0)


class VideoDetails:

    def __init__(self, title, index, resolution, m3u8url):
        self.title = title
        self.index = index
        w, h = resolution.split('x')
        self.w = int(w)
        self.h = int(h)
        self.m3u8url = m3u8url

    def __gt__(self, other):
        return self.w * self.h > other.w * other.h

    def __str__(self):
        return json.dumps(
            {
                'title': self.title,
                'm3u8url': self.m3u8url,
            },
            indent=2,
        )


class WebPageTools:

    def randomUserAgent(self):
        limit_size = len(USER_AGENTS) - 1
        randomint = random.randint(0, limit_size)

        headers = {'User-Agent': USER_AGENTS[randomint]}

        return headers

    def _getReqObj(self, url):
        ua = self.randomUserAgent()
        request = Request(url, headers=ua)
        return request

    def getHtmlStr(self, url):
        req_obj = self._getReqObj(url)
        html_str = urlopen(req_obj).read().decode()
        return html_str

    def getBsFromUrl(self, url):
        html_str = self.getHtmlStr(url)
        beautifulSoup = BeautifulSoup(html_str, 'html.parser')
        return beautifulSoup


class EPDownloader(WebPageTools):

    def __init__(
        self,
        outputdir,
        tempdir,
        log_path,
        poolsize=multiprocessing.cpu_count() - 1,
    ):
        self.outputdir = outputdir
        self.tempdir = tempdir
        self.log_path = log_path
        self.poolsize = poolsize
        self.logger = getLogger(log_path)

    def m3u8download(
        self,
        vedioDetails: VideoDetails,
        save_folder_path,
        tempdir,
    ):
        m3u8url = vedioDetails.m3u8url

        os.makedirs(os.path.dirname(save_folder_path), exist_ok=True)
        downloader = AioM3u8Downloader(
            m3u8url,
            save_folder_path,
            tempdir=tempdir,
            poolsize=self.poolsize,
            auto_rename=True,
        )
        # Running: ['ffmpeg', '-loglevel', 'warning', '-allowed_extensions', 'ALL', '-i', 'D:\\TBT\\zip\\f\\Running Man 20220703#0\\20220703\\lNLxcG00\\1100kb\\hls\\playlist_up.m3u8', '-acodec', 'copy', '-vcodec', 'copy', '-bsf:a', 'aac_adtstoasc', 'D:\\TBT\\zip\\Running Man 20220703#0.mp4']
        downloader.start()

    def get_vedio_info(self, browser: webdriver.Chrome):
        retry = 10
        for i in range(retry):
            try:
                m3u8url = browser.execute_script('return m3u8url')

            except JavascriptException:
                if i + 1 == retry:
                    self.logger.info('Failed return m3u8url')
                    return '0x0', ''

                self.logger.info(f'try: {i+1}')
                time.sleep(1)
        try:
            self.logger.info(f'query m3u8: {m3u8url}')
            m3u8_text = self.getHtmlStr(m3u8url)

            pattern = re.compile(r'RESOLUTION=([0-9]+x[0-9]+)')
            mo = pattern.search(m3u8_text)
            if mo is None:
                resolution = '1280x720'
            else:
                resolution = mo.group(1)
            return resolution, m3u8url
        except Exception as e:
            self.logger.info('--------------------------------')
            self.logger.info(f'e: {e}')
            self.logger.info(f'm3u8url: {m3u8url}')
            self.logger.info('--------------------------------')
            return '0x0', m3u8url

    def get_page_vedio_data_list(
        self,
        browser: webdriver.Chrome,
        url,
    ) -> "list[VideoDetails]":
        video_data_list = []
        browser.get(url)

        for index in range(LIMIT_GET_PAGE_VIDEO):
            a_list = browser.find_element(
                by=By.CLASS_NAME,
                value='holder.scrollbarx',
            ).find_elements(by=By.TAG_NAME, value='a')
            a_list[index].click()
            title = browser.find_element(
                by=By.CLASS_NAME,
                value='title.sizing',
            ).find_element(by=By.TAG_NAME, value='h1').text

            bros_iframe = browser.find_element(
                by=By.ID,
                value='video-player',
            ).find_element(
                by=By.TAG_NAME,
                value='iframe',
            )
            max_index = int(a_list[-1].get_attribute('href').split('#')[-1])

            browser.switch_to.frame(bros_iframe)
            resolution, m3u8url = self.get_vedio_info(browser)
            browser.switch_to.parent_frame()

            video_data_list.append(
                VideoDetails(title, index, resolution, m3u8url))
            if index == max_index:
                break
        return video_data_list

    def find_best_video_data(self, video_data_list: list[VideoDetails]):
        for high_quality_host in HIGH_QUALITY_HOST:
            for video_data in video_data_list:
                if high_quality_host in video_data.m3u8url:
                    return video_data
        return max(video_data_list)

    def find_title_list(self, mix_a_bs_list, his_weekday_pattern):
        title_list = []
        for aBs in mix_a_bs_list:
            text = aBs.text
            if text.startswith('======'):
                continue
            dateStr = text[text.rfind(' ') + 1:]
            _weekday = dat.strptime(dateStr, '%Y%m%d').weekday()
            if str(_weekday) not in his_weekday_pattern:
                continue
            title_list.append(text)
        return title_list

    def find_best_videos_from_episodes_page(
        self,
        browser,
        missing_title_list,
        program_info_url,
    ):
        best_video_details_list = []
        for missing_title in missing_title_list:
            yyyymmdd = missing_title.split()[-1]
            page_url = f'{program_info_url}{yyyymmdd}.html'
            video_data_list = self.get_page_vedio_data_list(browser, page_url)

            best_video_details = self.find_best_video_data(video_data_list)
            best_video_details_list.append(best_video_details)
        return best_video_details_list

    def parser(self, browser: webdriver.Chrome, program_info_url):
        with open(HIS_FILE_PATH, 'r', encoding='utf-8') as f:
            his_dict = json.load(f)
        his_info_dict = his_dict.get(program_info_url, {})
        his_weekday_pattern = his_info_dict.get(
            'weekdayPattern',
            '0|1|2|3|4|5|6',
        )
        his_titles = his_info_dict.get('titles', [])

        self.logger.info(f'query url: {program_info_url}')
        bs = self.getBsFromUrl(program_info_url)
        mix_a_bs_list = bs.find('div', class_='items sizing').find_all(
            attrs={"rel": "nofollow noopener noreferrer"})

        title_list = self.find_title_list(mix_a_bs_list, his_weekday_pattern)
        if not title_list:
            raise RuntimeError('cannot get title list')

        title_0 = title_list[0]
        top_title = title_0[:title_0.rfind(' ')]

        missing_title_list = list(set(title_list) - set(his_titles))

        # Find best videos from `episodes` page
        best_video_details_list = self.find_best_videos_from_episodes_page(
            browser, missing_title_list, program_info_url)

        # Download videos
        download_success_title_list = []
        for best_video_details in best_video_details_list:
            self.logger.info(
                '---------------------------------------------------')
            try:
                title = best_video_details.title
                index = best_video_details.index
                save_folder_path = Path(
                    os.path.join(
                        self.outputdir,
                        top_title,
                        f'{title}#{index}.mp4',
                    )).as_posix()

                downloaded_path = self.m3u8download(
                    best_video_details,
                    save_folder_path,
                    self.tempdir,
                )
                download_success_title_list.append(best_video_details.title)
                NotifyHook(
                    top_title,
                    title,
                    downloaded_path,
                    open_short_name='播放',
                ).pop()
            except Exception as e:
                self.logger.warning(f'Failed m3u8download: {e}')
                self.logger.warning(traceback.format_exc())
                self.logger.warning(f'{best_video_details}')
                NotifyHook(
                    top_title,
                    title,
                    self.log_path,
                    description='下載失敗',
                    open_short_name='打開log',
                ).pop()
            self.logger.info(
                '---------------------------------------------------')

        len_success = len(download_success_title_list)
        len_try = len(best_video_details_list)
        self.logger.info(f'Vedio downloaded: {len_success} / {len_try}')

        # Save history
        latest_his_dict = {
            program_info_url: {
                **his_info_dict,
                'name': top_title,
                'weekdayPattern': his_weekday_pattern,
                'titles': download_success_title_list + his_titles,
            }
        }
        his_dict.update(latest_his_dict)
        with open(HIS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(his_dict, f, indent=2, ensure_ascii=False)

    def run(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("--incognito")
        options.add_argument('--disable-gpu')
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")

        browser = webdriver.Chrome(
            service=Service('chromedriver.exe'),
            options=options,
        )
        for subscription_url in SUBSCRIPTION_URL_LIST:
            self.logger.info(f'=>> parser: {subscription_url}')
            self.parser(browser, subscription_url)
        browser.quit()


def main():
    parser = argparse.ArgumentParser(
        prog='video_downloader',
        description="download video at m3u8 url of contain png",
    )

    parser.add_argument(
        '--outputdir',
        '-od',
        required=True,
        help='output directory, e.g. ~/Downloads/',
    )
    parser.add_argument(
        '--tempdir',
        required=True,
        help='temp dir, used to store .ts files before combing them into mp4',
    )
    parser.add_argument(
        '--concurrency',
        '-c',
        metavar='N',
        type=int,
        default=multiprocessing.cpu_count() - 1,
        help='number of fragments to download at a time',
    )
    args = parser.parse_args()

    outputdir = Path(args.outputdir).as_posix()
    tempdir = Path(args.tempdir).as_posix()

    log_path = os.path.join(tempdir, 'episode_downloader.log')
    logger = getLogger(log_path)

    os.makedirs(tempdir, exist_ok=True)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start = time.time()
    epDownloader = EPDownloader(
        outputdir,
        tempdir,
        args.concurrency,
        log_path,
        logger=logger,
    )
    epDownloader.run()
    end = time.time()
    logger.info(f'=> {end - start} seconds')


if __name__ == '__main__':
    main()
    outputdir = 'D:\\TBT\\zip\\download video'
    tempdir = 'D:\\TBT\\zip\\download video\\temp'
    log_path = os.path.join(tempdir, 'episode_downloader.log')
    epDownloader = EPDownloader(
        outputdir,
        tempdir,
        log_path,
    )
    epDownloader.run()