import argparse
import json
import os
import time
import traceback
from datetime import datetime as dat
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from tool.epdownloader.epdownloader.base import WebTools
from tool.epdownloader.epdownloader.showQ import ShowQParser
from tool.epdownloader.epdownloader.utils import Log, Toast


class EPDownloader(WebTools):

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
        self.logger = logger
        self.limit_conn = limit_conn
        self.poolsize = poolsize

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

    def parser(self, browser: webdriver.Chrome, ep_url):
        history_info = self.cache_info.get(ep_url, {})
        expected_weekday = self.subscription_info[ep_url]
        parser = ShowQParser(
            outputdir=self.outputdir,
            tempdir=self.tempdir,
            log_path=self.log_path,
            logger=self.logger,
            limit_conn=self.limit_conn,
            poolsize=self.poolsize,
            limit_get_page_video=self.limit_get_page_video,
            priority_host_list=self.priority_host_list,
        )
        latest_cache_info = parser.parse(
            browser,
            ep_url,
            history_info,
            expected_weekday,
        )
        self.cache_info[ep_url] = latest_cache_info
        with open(self.cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(
                self.cache_info,
                f,
                indent=2,
                ensure_ascii=False,
            )

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
