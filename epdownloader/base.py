import json
import random
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from config import USER_AGENTS


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
