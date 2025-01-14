from threading import Thread
from trakt_scrobbler import logger
from trakt_scrobbler import trakt_interface as trakt
from trakt_scrobbler.notifier import notify


class Scrobbler(Thread):
    """Scrobbles the data from queue to Trakt."""

    def __init__(self, scrobble_queue, backlog_cleaner):
        super().__init__(name='scrobbler')
        logger.info('Started scrobbler thread.')
        self.scrobble_queue = scrobble_queue
        self.backlog_cleaner = backlog_cleaner
        self.prev_scrobble = None

    def run(self):
        while True:
            scrobble_item = self.scrobble_queue.get()
            self.scrobble(*scrobble_item)
            self.scrobble_queue.task_done()

    def _is_resume(self, verb, media_info):
        if not self.prev_scrobble or verb != "start":
            return False
        prev_verb, prev_data = self.prev_scrobble
        return prev_verb == "pause" and prev_data['media_info'] == media_info

    def _determine_category(self, verb, media_info, trakt_action):
        verb = verb if trakt_action == "scrobble" else trakt_action
        return 'resume' if self._is_resume(verb, media_info) else verb

    def handle_successful_scrobble(self, verb, data, resp):
        if 'movie' in resp:
            name = resp['movie']['title']
        else:
            name = (resp['show']['title'] +
                    " S{season:02}E{number:02}".format(**resp['episode']))
        category = self._determine_category(verb, data['media_info'], resp['action'])
        msg = f"Scrobble {category} successful for {name} at {resp['progress']:.2f}%"
        logger.info(msg)
        notify(msg, category=f"scrobble.{category}")
        self.backlog_cleaner.clear()

    def scrobble(self, verb, data):
        logger.debug(f"Scrobbling {verb} at {data['progress']:.2f}% for "
                     f"{data['media_info']['title']}")
        resp = trakt.scrobble(verb, **data)
        if resp:
            self.handle_successful_scrobble(verb, data, resp)
        elif resp is False and verb == 'stop' and data['progress'] > 80:
            logger.warning('Scrobble unsuccessful. Will try again later.')
            self.backlog_cleaner.add(data)
        else:
            logger.warning('Scrobble unsuccessful. Discarding it.')
        self.prev_scrobble = (verb, data)
