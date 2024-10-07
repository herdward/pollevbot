import requests
import logging
import time

logger = logging.getLogger(__name__)

class PollBot:
    def __init__(self, user: str, password: str, host: str,
                 login_type: str = 'pollev', min_option: int = 0,
                 max_option: int = None, closed_wait: float = 5,
                 open_wait: float = 5, lifetime: float = float('inf')):
        self.user = user
        self.password = password
        self.host = host
        self.login_type = login_type
        self.min_option = min_option
        self.max_option = max_option
        self.closed_wait = closed_wait
        self.open_wait = open_wait
        self.lifetime = lifetime
        self.start_time = time.time()

        self.session = requests.Session()
        self.session.headers = {
            'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36"
        }
        self.answered_polls = set()

    def _get_csrf_token(self) -> str:
        url = "https://www.polleverywhere.com/csrf_token"
        response = self.session.get(url)
        csrf_token = response.json().get('token')
        logger.info(f"Retrieved CSRF token: {csrf_token}")
        return csrf_token

    def _pollev_login(self) -> bool:
        """
        Logs into PollEv through pollev.com. Returns True on success, False otherwise.
        """
        logger.info(f"Logging into PollEv with user: {self.user}")

        csrf_token = self._get_csrf_token()
        login_url = "https://www.polleverywhere.com/login"
        data = {'login': self.user, 'password': self.password}
        headers = {'x-csrf-token': csrf_token}
        
        response = self.session.post(login_url, data=data, headers=headers)
        
        # Log response to debug if login worked properly
        logger.info(f"Login response status code: {response.status_code}")
        logger.info(f"Login response text: {response.text}")

        # If login is successful, PollEv sends an empty HTTP response.
        return response.status_code == 200 and not response.text

    def login(self):
        """Logs into PollEv using the selected login method."""
        success = self._pollev_login()
        if not success:
            raise LoginError("Your username or password was incorrect.")
        logger.info("Login successful.")

    def get_new_poll_id(self) -> Optional[str]:
        url = f"https://www.polleverywhere.com/firehose/{self.host}.json"
        try:
            response = self.session.get(url, timeout=0.3)
            logger.info(f"Polling response status: {response.status_code}")
            poll_id = response.json().get('message', {}).get('uid')
            if poll_id and poll_id not in self.answered_polls:
                self.answered_polls.add(poll_id)
                logger.info(f"Found new poll: {poll_id}")
                return poll_id
        except Exception as e:
            logger.error(f"Error getting poll: {e}")
        return None

    def answer_poll(self, poll_id) -> dict:
        import random
        poll_url = f"https://www.polleverywhere.com/polls/{poll_id}.json"
        response = self.session.get(poll_url)
        poll_data = response.json()
        logger.info(f"Poll data: {poll_data}")

        options = poll_data.get('options', [])[self.min_option:self.max_option]
        if not options:
            logger.error("No options available to answer.")
            return {}

        option_id = random.choice(options)['id']
        logger.info(f"Selected option ID: {option_id}")
        
        response = self.session.post(
            f"https://www.polleverywhere.com/polls/{poll_id}/responses",
            headers={'x-csrf-token': self._get_csrf_token()},
            data={'option_id': option_id, 'isPending': True, 'source': "pollev_page"}
        )
        logger.info(f"Response after answering poll: {response.json()}")
        return response.json()

    def run(self):
        """Runs the bot."""
        try:
            self.login()
        except LoginError as e:
            logger.error(e)
            return
        
        while self.alive():
            poll_id = self.get_new_poll_id()
            if poll_id:
                logger.info(f"Answering poll {poll_id}")
                self.answer_poll(poll_id)
                time.sleep(self.open_wait)
            else:
                logger.info(f"No new polls, waiting {self.closed_wait} seconds.")
                time.sleep(self.closed_wait)
