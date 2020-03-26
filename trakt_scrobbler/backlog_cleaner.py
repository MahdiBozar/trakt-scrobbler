import confuse
import time
from threading import Timer
from trakt_scrobbler import config, logger
from trakt_scrobbler.app_dirs import DATA_DIR
from trakt_scrobbler.utils import read_json, write_json
from trakt_scrobbler import trakt_interface as trakt

BACKLOG_PATH = DATA_DIR / "watched_backlog.json"


class BacklogCleaner:
    def __init__(self, manual=False):
        self.backlog = []
        self.clear_interval = config["backlog"]["clear_interval"].get(confuse.Number())
        self.expiry = config["backlog"]["expiry"].get(confuse.Number())
        self.timer_enabled = not manual
        if self.timer_enabled:
            self._make_timer()
            self.clear()

    def remove_expired(self):
        not_expired = []
        for item in self.backlog:
            if item["updated_at"] + self.expiry > time.time():
                not_expired.append(item)
        self.backlog = not_expired
        write_json(self.backlog, BACKLOG_PATH)

    def _make_timer(self):
        self.timer = Timer(self.clear_interval, self.clear)
        self.timer.name = "backlog_cleaner"
        self.timer.start()

    def add(self, data):
        self.backlog.append(data)
        write_json(self.backlog, BACKLOG_PATH)

    def clear(self):
        self.backlog = read_json(BACKLOG_PATH) or []
        self.remove_expired()

        failed = []
        for item in self.backlog:
            logger.debug(f'Adding item to history {item}')
            if trakt.add_to_history(**item):
                logger.info("Successfully added media to history.")
            else:
                failed.append(item)

        self.backlog = failed
        write_json(self.backlog, BACKLOG_PATH)

        if self.timer_enabled:
            self.timer.cancel()
            self._make_timer()
