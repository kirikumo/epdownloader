import json
import random
import requests

from bs4 import BeautifulSoup

from config import USER_AGENTS


class WebTools:

    def randomUserAgent(self):
        limit_size = len(USER_AGENTS) - 1
        randomint = random.randint(0, limit_size)

        headers = {'User-Agent': USER_AGENTS[randomint]}

        return headers

    def _getReqObj(self, url):
        ua = self.randomUserAgent()
        request = requests.get(url, headers=ua)
        return request

    def getHtmlStr(self, url):
        req_obj = self._getReqObj(url)
        html_str = req_obj.text
        return html_str

    def getContent(self, url):
        req_obj = self._getReqObj(url)
        if req_obj.status_code == 200:
            return req_obj.content
        else:
            return None

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
