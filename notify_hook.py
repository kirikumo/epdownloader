import os
import sys
import threading
from functools import partial

import winotify


class NotifyHook:

    def __init__(
        self,
        app_name,
        title,
        vedio_path,
        description='下載完成',
        icon=os.path.join(os.path.dirname(__file__), 'notification.ico'),
        open_short_name='打開',
    ):
        self.title = title
        self.vedio_path = vedio_path
        self.description = description
        self.icon = icon
        self.open_short_name = open_short_name

        self.notifier = self.init_notifier(app_name)
        self.notifier.start()

    def init_notifier(self, app_name):
        app_id = app_name
        app_path = os.path.abspath(__file__)

        registry = winotify.Registry(
            app_id,
            winotify.PY_EXE,
            app_path,
            force_override=True,
        )
        return winotify.Notifier(registry)

    # def play_video(self, vedio_path):
    #     os.startfile(vedio_path)
    #     self.loop_update = False
    #     sys.exit()

    def quit(self):
        sys.exit()

    # def listen(self):
    #     while self.loop_update:
    #         self.notifier.update()
    #         time.sleep(3)
    #         print("i'm running")

    #         if self.stop_datetime and dat.now() > self.stop_datetime:
    #             break

    #     t = self.notifier.create_notification("Timeout")
    #     t.add_actions(label='saf', launch=self.vedio_path)
    #     t.show()

    def pop_and_listen(self):
        # pt = partial(self.play_video, self.vedio_path)
        # pt.__name__ = self.play_video.__name__

        toast = self.notifier.create_notification(
            self.title,
            self.description,
            icon=self.icon,
            launch=self.vedio_path,
            # launch=self.notifier.register_callback(pt),
        )
        toast.add_actions(
            # "播放",
            self.open_short_name,
            launch=self.vedio_path,
            # self.notifier.register_callback(pt),
        )

        # ptq = partial(self.quit)
        # ptq.__name__ = self.quit.__name__
        toast.add_actions("知道")
        toast.show()
        # self.listen()

    def pop(self):
        thread = threading.Thread(target=self.pop_and_listen)
        thread.start()


if __name__ == "__main__":
    app_name = 'downloader'
    title = 'RM'
    vedio_path = 'D:\TBT\zip\download video\Running Man\Running Man 20220710#9.mp4'
    # icon = 'D:\\Hin\\python\\tool\\episode_downloader\\python.ico'
    # description = '下載完成'
    notiHook = NotifyHook(
        app_name,
        title,
        vedio_path,
        # description,
        # icon,
    )
    notiHook.pop()
