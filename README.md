# epdownloader

epdownloader is a tool for download latest or missing episodes.

epdownloader use on Windows 10 will be better

Note: this README is for Windows 10

## Download

[ffmpeg](https://ffmpeg.org/download.html)
version 4.1 or later.

``` bash
# check
ffmpeg -version
```

[chromedriver](https://www.selenium.dev/documentation/webdriver/getting_started/install_drivers/)
match your chrome version

## Environment

``` bash
# install requirements
pip install -r requirements.txt
# if get 'UnicodeDecodeError: 'utf-8' codec can't decode byte ...' message
# try:
chcp 65001
pip install -r requirements.txt
```

## Quick Start

``` bash
# python epdownloader.py --outputdir $outputdir --tempdir $tempdir --config_path $config_file --programlock --pop_notification
python epdownloader.py -od ./my_episodes --tempdir ./my_episodes/temp --config_path ./my_episodes/config.json -lock -pop
```

## Configuration File

- `subscription_info`
  - `$episodes_list_page_url` : Episodes list page url. Only support host https://newsofcar.net/ url
  - `$expected_weekday`:
    - Monday to Sunday : "0|1|2|3|4|5|6"
    - Monday and Sunday : "0|6"
    - Sunday : "6"
- `priority_host_list`
  - Priority download max resolution : []
  - Priority download https://xxyy.com/index.m3u8 : ["xxyy.com"] or [https://xxyy.com]
- `limit_get_page_video` : Limit number of get page video info
- `cache_file_path` : Cache file path. Automatic create if file not exists
- `chromedriver_path` : Chromedriver path

### Example (config.json)

``` python
{
    "subscription_info": {
        "https://newsofcar.net/running-man/": "6"
    },
    "priority_host_list": [
        "vip.lz-cdn11.com",
        "dy2.yle888.vip",
        "c2.monidai.com"
    ],
    "limit_get_page_video": 20,
    "cache_file_path": "{path}/vedio_his.json",
    "chromedriver_path": "{path}/chromedriver.exe"
}
```

## Command line

``` text
usage: video_downloader [-h] --outputdir OUTPUTDIR --tempdir TEMPDIR --config_path CONFIG_PATH 
                        [--concurrency N] [--limit_conn LIMIT_CONN] [--programlock]
                        [--pop_notification]

download latest or missing episodes

optional arguments:
  -h, --help            show this help message and exit
  --outputdir OUTPUTDIR, -od OUTPUTDIR
                        output directory, e.g. ~/Downloads/
  --tempdir TEMPDIR     temp dir, used to store .ts files before combing them into mp4
  --config_path CONFIG_PATH
                        custom config file path, e.g. ~/config.json
  --concurrency N, -c N
                        number of save ts file at a time
  --limit_conn LIMIT_CONN, -conn LIMIT_CONN
                        limit amount of simultaneously opened connections
  --programlock, -lock  set to ensure that it can't be called again until the program is done
  --pop_notification, -pop
                        set to allow pop notifications (only support Windows 10 with PowerShell)

```

## Made Simpler

### .bat

``` bat
@echo off
chcp 65001
SET output_dir=%~dp0
SET temp_dir=%output_dir%temp

echo *********************************************
echo output_dir: %output_dir:~0,-1%
echo temp_dir: %temp_dir%
echo *********************************************

set config_file=.\config.json

python epdownloader.py -od "%output_dir:~0,-1%" --tempdir "%temp_dir%" --config_path "%config_file%" -lock -pop

```

## License

[GPLv3](https://github.com/kirikumo/epdownloader/blob/main/LICENSE)
