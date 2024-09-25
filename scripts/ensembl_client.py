import threading
import time
import sys
import json
import logging
import traceback
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import random

def truncate_text(text, max_length=500):
    """Truncate text to a maximum length with an ellipsis if needed."""
    if len(text) <= max_length:
        return text
    else:
        return text[:max_length] + '... [truncated]'

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
                    logging.debug(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                    time.sleep(sleep_time)
                # Reset count after sleeping
                EnsemblRestClient._req_count = 1
                EnsemblRestClient._last_reset = time.time()

    def perform_rest_action(self, endpoint, method='GET', hdrs=None, params=None, data=None, retries=5):
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

        for attempt in range(1, retries + 1):
            # Rate limiting
            self._check_rate_limit()

            try:
                request = Request(self.server + endpoint, data=data, headers=hdrs, method=method)
                with urlopen(request) as response:
                    status_code = response.getcode()
                    headers = response.headers
                    content = response.read()
                    if content:
                        result_data = json.loads(content)
                    else:
                        result_data = {}
                    logging.debug(f"Successful API call to {endpoint} on attempt {attempt}: Status {status_code}, Headers {dict(headers)}")
                    return result_data  # Success
            except HTTPError as e:
                error_content = None
                try:
                    error_content = e.read().decode('utf-8', errors='replace')
                except Exception as read_error:
                    logging.error(f"Error reading error content: {read_error}")
                truncated_error_content = truncate_text(error_content) if error_content else "No error content received."
                logging.error(f"HTTPError for endpoint {endpoint} on attempt {attempt}: Status code: {e.code} Reason: {e.reason}")
                logging.error(f"Error content for endpoint {endpoint} on attempt {attempt}: {truncated_error_content}")

                if e.code == 429:
                    retry_after = e.headers.get('Retry-After')
                    if retry_after:
                        try:
                            sleep_duration = float(retry_after)
                        except ValueError:
                            sleep_duration = 1
                    else:
                        sleep_duration = 1
                    # Introduce jitter
                    sleep_duration += random.uniform(0, 1)
                    logging.warning(f"HTTP 429 Too Many Requests for endpoint {endpoint}. Retrying after {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)
                    continue  # Retry the request
                elif e.code in [500, 502, 503, 504]:
                    retry_after = e.headers.get('Retry-After')
                    if retry_after:
                        try:
                            sleep_duration = float(retry_after)
                        except ValueError:
                            sleep_duration = 2 ** attempt
                    else:
                        sleep_duration = 2 ** attempt
                    # Introduce jitter
                    sleep_duration += random.uniform(0, 1)
                    logging.warning(f"HTTP {e.code} {e.reason} for endpoint {endpoint}. Retrying after {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)
                    continue
                elif e.code == 413:
                    # Payload Too Large
                    logging.error(f"Payload too large for endpoint {endpoint}. Consider reducing batch size.")
                    return {}
                else:
                    logging.error(f"Non-retryable HTTP error {e.code} for endpoint {endpoint}.")
                    return {}  # Non-retryable error
            except URLError as e:
                logging.error(f"URLError for endpoint {endpoint} on attempt {attempt}: {e.reason}")
                logging.debug(traceback.format_exc())
                if attempt < retries:
                    sleep_duration = 2 ** attempt + random.uniform(0, 1)
                    logging.info(f"Retrying endpoint {endpoint} in {sleep_duration:.2f} seconds...")
                    time.sleep(sleep_duration)
                    continue
                else:
                    logging.error(f"Max retries exceeded for endpoint {endpoint}.")
                    return {}
            except Exception as e:
                logging.error(f"Exception for endpoint {endpoint} on attempt {attempt}: {e}")
                logging.debug(traceback.format_exc())
                if attempt < retries:
                    sleep_duration = 2 ** attempt + random.uniform(0, 1)
                    logging.info(f"Retrying endpoint {endpoint} in {sleep_duration:.2f} seconds...")
                    time.sleep(sleep_duration)
                    continue
                else:
                    logging.error(f"Max retries exceeded for endpoint {endpoint}.")
                    return {}
