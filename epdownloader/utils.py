import logging
import os
import threading

from winotify import Notification


class Log:
    LOGGER: logging.Logger = None

    @classmethod
    def setup_logger(cls, filePath=None, level=logging.INFO):
        if cls.LOGGER is not None:
            raise Exception('already setup logger')
        logger = logging.getLogger('epdownloader')
        logger.handlers = []
        logger.setLevel(level)

        sh = logging.StreamHandler()
        sh.setFormatter(
            logging.Formatter('[%(asctime)s: %(levelname)s] %(message)s'))
        logger.addHandler(sh)

        if filePath is not None:
            os.makedirs(os.path.dirname(filePath), exist_ok=True)
            fh = logging.FileHandler(filePath)
            fh.setFormatter(
                logging.Formatter(
                    '[%(asctime)s: %(levelname)s] [%(filename)s:%(lineno)d] %(message)s'
                ))
            logger.addHandler(fh)

        cls.LOGGER = logger


class Toast:
    POP_NOTIFICATION = False

    @classmethod
    def pop_status(cls, pop_notification):
        cls.POP_NOTIFICATION = pop_notification

    @classmethod
    def pop(
        cls,
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
        if not cls.POP_NOTIFICATION: return
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
