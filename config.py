import os

SUBSCRIPTION_URL_LIST = [
    'https://newsofcar.net/running-man/',
    'https://newsofcar.net/what-playing/',
    'https://newsofcar.net/house-and-master/',
]
HIGH_QUALITY_HOST = [
    'vip.lz-cdn11.com',
    'dy2.yle888.vip',
    'c2.monidai.com',
]
LIMIT_GET_PAGE_VIDEO = 20

USER_AGENTS = [
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) '
    'Gecko/20071127 Firefox/2.0.0.11', 'Opera/9.25 (Windows NT 5.1; U; en)',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1;'
    ' .NET CLR 1.1.4322; .NET CLR 2.0.50727)',
    'Mozilla/5.0 (compatible; Konqueror/3.5;'
    ' Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.19 (KHTML, like Gecko) '
    'Chrome/18.0.1025.142 Safari/535.19',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:11.0)'
    ' Gecko/20100101 Firefox/11.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:8.0.1)'
    ' Gecko/20100101 Firefox/8.0.1',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.19 '
    '(KHTML, like Gecko) Chrome/18.0.1025.151 Safari/535.19',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0)'
    ' Gecko/20100101 Firefox/23.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0)'
    ' Gecko/20100101 Firefox/85.0'
]
HIS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'vedio_his.json')
