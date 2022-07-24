import argparse
import json
import os
import re
import time
import traceback
from datetime import datetime as dat
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir

from aiom3u8downloader.aiodownloadm3u8 import AioM3u8Downloader
from selenium import webdriver
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from tool.epdownloader.epdownloader.base import VideoData, WebPageTools
from tool.epdownloader.epdownloader.utils import Log, Toast


class EPDownloader(WebPageTools):

    def __init__(
        self,
        outputdir,
        tempdir,
        log_path,
        config_path,
        logger,
        limit_conn=100,
        poolsize=7,
    ):
        self.outputdir = outputdir
        self.tempdir = tempdir
        self.log_path = log_path
        self.poolsize = poolsize
        self.logger = logger
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
                Toast.pop(**noti_kwargs)
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
        # self.logger.info('---------------------- START ----------------------')

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
        # self.logger.info('----------------------- END -----------------------')


def _run(
    log_path,
    tempdir,
    outputdir,
    concurrency,
    limit_conn,
    config_path,
    logger: Log.LOGGER,
):
    start = time.time()
    epDownloader = EPDownloader(
        outputdir=outputdir,
        tempdir=tempdir,
        log_path=log_path,
        config_path=config_path,
        limit_conn=limit_conn,
        poolsize=concurrency,
        logger=logger,
    )
    try:
        epDownloader.run()
    except Exception as e:
        logger.exception(traceback.format_exc())
        logger.info('pop failure notification...')
        Toast.pop(
            app_id='epdownloader',
            title='不明執行失敗',
            link=log_path,
            button1_name='打開log',
            button1_link=log_path,
        )
    end = time.time()
    logger.info(f'=> {end - start} seconds')


def main():
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
        default=7,
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

    args = parser.parse_args()

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
    pop_notification = args.pop_notification

    Toast.pop_status(pop_notification)

    loc_file_path = os.path.join(gettempdir(), 'epdownloader')
    Log.setup_logger(log_path)
    logger = Log.LOGGER
    if os.path.exists(loc_file_path):
        logger.info('Protected program is running')
        logger.info('Program exit')
        return

    logger.info('---------------------- START ----------------------')
    if programlock:
        with NamedTemporaryFile() as tf:
            os.rename(tf.name, loc_file_path)
            _run(log_path, tempdir, outputdir, concurrency, limit_conn,
                 config_path, logger)
    else:
        _run(log_path, tempdir, outputdir, concurrency, limit_conn,
             config_path, logger)
    logger.info('----------------------- END -----------------------')


if __name__ == '__main__':
    main()
