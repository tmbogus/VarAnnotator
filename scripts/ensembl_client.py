import threading
import time
import sys
import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import logging

class EnsemblRestClient(object):
    _global_lock = threading.Lock()
    _req_count = 0
    _last_reset = time.time()

    def __init__(self, server='http://grch37.rest.ensembl.org', reqs_per_sec=15):
        self.server = server
        self.reqs_per_sec = reqs_per_sec

    def _check_rate_limit(self):
        with EnsemblRestClient._global_lock:
            current_time = time.time()
            elapsed = current_time - EnsemblRestClient._last_reset
            if elapsed >= 1:
                # Reset every second
                EnsemblRestClient._req_count = 0
                EnsemblRestClient._last_reset = current_time
            if EnsemblRestClient._req_count < self.reqs_per_sec:
                EnsemblRestClient._req_count += 1
                return
            else:
                # Sleep until the next second starts
                sleep_time = 1 - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                # Reset count after sleeping
                EnsemblRestClient._req_count = 1
                EnsemblRestClient._last_reset = time.time()

    def perform_rest_action(self, endpoint, method='GET', hdrs=None, params=None, data=None, retries=3):
        if hdrs is None:
            hdrs = {}

        if 'Content-Type' not in hdrs:
            hdrs['Content-Type'] = 'application/json'
        if 'Accept' not in hdrs:
            hdrs['Accept'] = 'application/json'

        if params:
            endpoint += '?' + urlencode(params)

        if data is not None and method == 'POST':
            if isinstance(data, dict):
                data = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                data = data.encode('utf-8')

        for attempt in range(retries):
            # Rate limiting
            self._check_rate_limit()

            try:
                request = Request(self.server + endpoint, data=data, headers=hdrs, method=method)
                response = urlopen(request)
                content = response.read()
                if content:
                    result_data = json.loads(content)
                else:
                    result_data = None
                return result_data  # Success
            except HTTPError as e:
                if e.code == 429:
                    retry_after = e.headers.get('Retry-After', '1')
                    logging.warning(f"HTTP 429 Too Many Requests for {endpoint}. Retrying after {retry_after} seconds.")
                    time.sleep(float(retry_after))
                    continue  # Retry the request
                else:
                    logging.error(f"Request failed for {endpoint}: Status code: {e.code} Reason: {e.reason}")
                    return None
            except URLError as e:
                logging.error(f"Request failed for {endpoint}: URLError: {e.reason}")
                if attempt < retries - 1:
                    backoff_time = 2 ** attempt  # Exponential backoff
                    logging.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    continue
                else:
                    logging.error(f"Max retries exceeded for {endpoint}")
                    return None
            except Exception as e:
                logging.error(f"Request failed for {endpoint}: Exception: {e}")
                if attempt < retries - 1:
                    backoff_time = 2 ** attempt
                    logging.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    continue
                else:
                    logging.error(f"Max retries exceeded for {endpoint}")
                    return None
