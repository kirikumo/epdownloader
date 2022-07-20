import argparse
import json
import multiprocessing
import os
import random
import re
import signal
import sys
import threading
import time
import traceback
from datetime import datetime as dat
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir
from urllib.request import Request, urlopen

from aiom3u8downloader.aiodownloadm3u8 import AioM3u8Downloader
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from tool.epdownloader.epdownloader.configlogger import setup_logger
from winotify import Notification

from config import USER_AGENTS

POP_NOTIFICATION = False

parser = argparse.ArgumentParser(
    prog='epdownloader',
    description="download latest or missing episodes",
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
    '--config_path',
    required=True,
    help='custom config file path, e.g. ~/config.json',
)
parser.add_argument(
    '--concurrency',
    '-c',
    metavar='N',
    type=int,
    default=multiprocessing.cpu_count() - 1,
    help='number of save ts file at a time',
)
parser.add_argument(
    '--limit_conn',
    '-conn',
    type=int,
    default=100,
    help='limit amount of simultaneously opened connections',
)
parser.add_argument(
    '--programlock',
    '-lock',
    action='store_true',
    help=
    "set to ensure that it can't be called again until the program is done",
)
parser.add_argument(
    '--pop_notification',
    '-pop',
    action='store_true',
    help=
    "set to allow pop notifications (only support Windows 10 with PowerShell)",
)


def pop_notification(
    app_id,
    title,
    link='',
    msg='',
    icon=os.path.join(os.path.dirname(__file__), 'notification.ico'),
    duration: str = 'short',  # short/long
    button1_name=None,
    button1_link=None,
    button2_name=None,
    button2_link=None,
):
    if not POP_NOTIFICATION: return
    toast = Notification(
        app_id=app_id,
        title=title,
        msg=msg,
        icon=icon,
        duration=duration,
        launch=link,
    )

    button_list = [
        (button1_name, button1_link),
        (button2_name, button2_link),
    ]
    for name, link in button_list:
        if not name:
            continue
        toast.add_actions(
            label=name,
            launch=link,
        )

    toast.add_actions(label='知道')
    thread = threading.Thread(target=toast.show())
    thread.start()
    thread.join()


def signal_handler(sig, frame):
    sys.exit(0)


class VideoData:

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
                'index': self.index,
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
        config_path,
        limit_conn=100,
        poolsize=multiprocessing.cpu_count() - 1,
    ):
        self.outputdir = outputdir
        self.tempdir = tempdir
        self.log_path = log_path
        self.poolsize = poolsize
        self.logger = setup_logger(log_path)
        self.limit_conn = limit_conn

        with open(config_path, encoding='utf-8') as f:
            config_dict = json.load(f)

        self.subscription_info: dict = config_dict['subscription_info']
        self.priority_host_list: list = config_dict['priority_host_list']
        self.limit_get_page_video: int = config_dict['limit_get_page_video']
        self.cache_file_path: str = Path(
            config_dict['cache_file_path']).as_posix()
        self.chromedriver_path = Path(
            config_dict['chromedriver_path']).as_posix()

        self.cache_info = {}
        if os.path.exists(self.cache_file_path):
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                self.cache_info = json.load(f)

        if not os.path.exists(self.chromedriver_path):
            raise FileExistsError(self.chromedriver_path)

    def m3u8download(
        self,
        vedioDetails: VideoData,
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
            limit_conn=self.limit_conn,
            auto_rename=True,
        )
        return downloader.start()

    def download(self, ep_name, video_data: VideoData):
        title = video_data.title
        index = video_data.index
        save_folder_path = Path(
            os.path.join(
                self.outputdir,
                ep_name,
                f'{title}#{index}.mp4',
            )).as_posix()

        downloaded_path = self.m3u8download(
            video_data,
            save_folder_path,
            self.tempdir,
        )
        return downloaded_path

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
    ) -> "list[VideoData]":
        video_data_list = []
        browser.get(url)

        for index in range(self.limit_get_page_video):
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

            browser.switch_to.frame(bros_iframe)
            resolution, m3u8url = self.get_vedio_info(browser)
            browser.switch_to.parent_frame()

            _videoData = VideoData(title, index, resolution, m3u8url)
            video_data_list.append(_videoData)

            max_num_source = int(
                a_list[-1].get_attribute('href').split('#')[-1])
            if index == max_num_source:
                break
        return video_data_list

    def find_title_list(self, mix_a_bs_list, expected_weekday):
        title_list = []
        for aBs in mix_a_bs_list:
            text = aBs.text
            if text.startswith('======'):
                continue
            dateStr = text[text.rfind(' ') + 1:]
            _weekday = dat.strptime(dateStr, '%Y%m%d').weekday()
            if str(_weekday) not in expected_weekday.split('|'):
                continue
            title_list.append(text)
        return title_list

    def find_best_video_data(self, video_data_list: list[VideoData]):
        for priority_host in self.priority_host_list:
            for video_data in video_data_list:
                if priority_host in video_data.m3u8url:
                    return video_data
        return max(video_data_list)

    def parser(self, browser: webdriver.Chrome, ep_url):
        cache_info = self.cache_info.get(ep_url, {})
        expected_weekday = self.subscription_info[ep_url]  # '0|1|2|3|4|5|6'
        his_title_list = cache_info.get('titles', [])

        bs = self.getBsFromUrl(ep_url)
        mix_a_bs_list = bs.find('div', class_='items sizing').find_all(
            attrs={"rel": "nofollow noopener noreferrer"})

        title_list = self.find_title_list(mix_a_bs_list, expected_weekday)
        if not title_list:
            raise RuntimeError('cannot get title list')

        title_0 = title_list[0]
        ep_name = title_0[:title_0.rfind(' ')]

        missing_title_list = list(
            filter(lambda title: not title in his_title_list, title_list))

        # Download missing episodes
        downloaded_title_list = []
        for missing_title in missing_title_list:

            yyyymmdd = missing_title.split()[-1]
            url = f'{ep_url}{yyyymmdd}.html'
            video_data_list = self.get_page_vedio_data_list(browser, url)
            best_video_data = self.find_best_video_data(video_data_list)

            try:
                downloaded_path = self.download(ep_name, best_video_data)
                downloaded_title_list.append(best_video_data.title)
                self.logger.info('pop success notification...')
                noti_kwargs = dict(
                    app_id=ep_name,
                    title=missing_title,
                    msg='下載完成',
                    link=downloaded_path,
                    button1_name='播放',
                    button1_link=downloaded_path,
                )
            except Exception as e:
                self.logger.warning(traceback.format_exc())
                self.logger.warning(f'{best_video_data}')
                self.logger.info('pop failure notification...')
                noti_kwargs = dict(
                    app_id=ep_name,
                    title=missing_title,
                    msg='下載失敗',
                    link=self.log_path,
                    button1_name='打開log',
                    button1_link=self.log_path,
                )
            try:
                pop_notification(**noti_kwargs)
            except Exception as e:
                self.logger.warning('Send notification failed')
                self.logger.warning(traceback.format_exc())

        # Log message
        len_success = len(downloaded_title_list)
        len_try = len(missing_title_list)
        self.logger.info(f'Downloaded episode: {len_success} / {len_try}')

        # Save history
        his_title_list = downloaded_title_list + his_title_list
        his_title_list.sort(reverse=True)
        latest_his_dict = {
            ep_url: {
                **cache_info,
                'name': ep_name,
                'titles': his_title_list,
            }
        }
        self.cache_info.update(latest_his_dict)
        with open(self.cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache_info, f, indent=2, ensure_ascii=False)

    def run(self):
        self.logger.info('---------------------- START ----------------------')

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("--incognito")
        options.add_argument('--disable-gpu')
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")

        browser = webdriver.Chrome(
            service=Service(executable_path=self.chromedriver_path),
            options=options,
        )
        for subscription_url in self.subscription_info.keys():
            self.logger.info(
                '===================================================')
            self.logger.info(f'=>> parser: {subscription_url}')
            self.parser(browser, subscription_url)
            self.logger.info(
                '===================================================')
        browser.quit()
        self.logger.info('----------------------- END -----------------------')


def _run(log_path, tempdir, outputdir, concurrency, limit_conn, config_path):
    logger = setup_logger(log_path)

    start = time.time()
    epDownloader = EPDownloader(
        outputdir=outputdir,
        tempdir=tempdir,
        log_path=log_path,
        config_path=config_path,
        limit_conn=limit_conn,
        poolsize=concurrency,
    )
    # notifyHook = NotifyHook(app_name='epdownloader')
    try:
        # pop_notification(app_id='epdownloader', title='執行中...')
        epDownloader.run()
        # pop_notification(app_id='epdownloader', title='執行結束')
    except Exception as e:
        logger.exception(traceback.format_exc())
        logger.info('pop failure notification...')
        pop_notification(
            app_id='epdownloader',
            title='不明執行失敗',
            link=log_path,
            button1_name='打開log',
            button1_link=log_path,
        )
    end = time.time()
    logger.info(f'=> {end - start} seconds')


def main(args):
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # args = parser.parse_args()

    tempdir = Path(args.tempdir).as_posix()
    os.makedirs(tempdir, exist_ok=True)
    log_path = os.path.join(
        tempdir,
        f'ep_{dat.strftime(dat.now(), "%Y%m%d")}.log',
    )
    outputdir = Path(args.outputdir).as_posix()
    config_path = args.config_path
    concurrency = args.concurrency
    programlock = args.programlock
    limit_conn = args.limit_conn
    # pop_notification = args.pop_notification

    # if not os.path.exists(config_path):
    #     raise FileExistsError

    loc_file_path = os.path.join(gettempdir(), 'epdownloader')
    if os.path.exists(loc_file_path):
        logger = setup_logger(log_path)
        logger.info('Protected program is running')
        logger.info('Program exit')
        return

    if programlock:
        with NamedTemporaryFile() as tf:
            os.rename(tf.name, loc_file_path)
            _run(log_path, tempdir, outputdir, concurrency, limit_conn,
                 config_path)
    else:
        _run(log_path, tempdir, outputdir, concurrency, limit_conn,
             config_path)


if __name__ == '__main__':
    args = parser.parse_args()
    POP_NOTIFICATION = args.pop_notification
    main(args)
