import json
import logging
import os
import re
import time
import traceback
from datetime import datetime as dat
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.common.by import By
from aiom3u8downloader.aiodownloadm3u8 import AioM3u8Downloader
from tool.epdownloader.epdownloader.base import VideoData, WebTools
from tool.epdownloader.epdownloader.utils import Toast


class ShowQParser:

    def __init__(
        self,
        outputdir,
        tempdir,
        log_path,
        logger: logging.Logger,
        limit_get_page_video,
        priority_host_list,
        limit_conn=100,
        poolsize=5,
    ):
        self.outputdir = outputdir
        self.tempdir = tempdir
        self.log_path = log_path
        self.logger = logger
        self.limit_get_page_video = limit_get_page_video
        self.priority_host_list = priority_host_list
        self.limit_conn = limit_conn
        self.poolsize = poolsize

        self.web_tools = WebTools()

    # TODO: move to WebTools
    def download_m3u8(self, ep_name, video_data: VideoData):
        title = video_data.title
        index = video_data.index
        m3u8url = video_data.m3u8url
        save_folder_path = Path(
            os.path.join(
                self.outputdir,
                ep_name,
                f'{title}#{index}.mp4',
            )).as_posix()
        os.makedirs(os.path.dirname(save_folder_path), exist_ok=True)

        downloader = AioM3u8Downloader(
            m3u8url,
            save_folder_path,
            tempdir=self.tempdir,
            poolsize=self.poolsize,
            limit_conn=self.limit_conn,
            auto_rename=True,
        )
        return downloader.start()

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
            m3u8_text = self.web_tools.getHtmlStr(m3u8url)

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

    def find_title_list(self, mix_a_bs_list, expected_weekday) -> list[str]:
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

    def parse(
        self,
        browser: webdriver.Chrome,
        ep_url,
        history_info: dict,
        expected_weekday,
    ):
        # cache_info = self.cache_info.get(ep_url, {})
        # expected_weekday = self.subscription_info[ep_url]  # '0|1|2|3|4|5|6'
        his_title_list = history_info.get('titles', [])

        bs = self.web_tools.getBsFromUrl(ep_url)
        mix_a_bs_list = bs.find('div', class_='items sizing').find_all(
            attrs={"rel": "nofollow noopener noreferrer"})

        title_list = self.find_title_list(mix_a_bs_list, expected_weekday)
        if not title_list:
            raise RuntimeError('cannot find title list')

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
                downloaded_path = self.download_m3u8(ep_name, best_video_data)
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

        # latest history
        his_title_list = downloaded_title_list + his_title_list
        his_title_list.sort(reverse=True)

        return {
            **history_info,
            'name': ep_name,
            'titles': his_title_list,
        }
