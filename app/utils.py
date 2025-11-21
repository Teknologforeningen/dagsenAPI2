import requests
import os
import datetime
from dotenv import load_dotenv
from flask import Response, request, render_template
from typing import Dict, List, Any
import json
import copy
import time
import random
import email.utils as email_utils
import threading
import logging

days = {
  'sv': [' ', u'Måndag', u'Tisdag', u'Onsdag', u'Torsdag', u'Fredag', u'Lördag', u'Söndag'],
  'en': [' ', u'Monday', u'Tuesday', u'Wednesday', u'Thursday', u'Friday', u'Saturday', u'Sunday'],
  'fi': [' ', u'Maanantai', u'Tiistai', u'Keskiviikko', u'Torstai', u'Perjantai', u'Lauantai', u'Sunnuntai'],
}


# Very small in-process token-bucket rate limiter (per-process)
class SimpleRateLimiter:
    def __init__(self, rate: float = 1, per_seconds: float = 1.0):
        # rate = tokens per per_seconds
        self.capacity = float(rate)
        self.tokens = float(rate)
        self.fill_rate = float(rate) / float(per_seconds)
        self.timestamp = time.time()
        self.lock = threading.Lock()

    def _add_tokens(self):
        now = time.time()
        elapsed = now - self.timestamp
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        self.timestamp = now

    def allow(self) -> bool:
        with self.lock:
            self._add_tokens()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    def acquire(self, block: bool = True, sleep_interval: float = 0.05) -> bool:
        """Block until a token is available (or return False if not blocking)."""
        if not block:
            return self.allow()
        while True:
            if self.allow():
                return True
            time.sleep(sleep_interval)


# General class for the api client
class APIClient:

    # Set variables from env
    def __init__(self):
        load_dotenv(override=True)
        self.api_base_url: str = os.getenv("API_BASE_URL")
        self.menu_name = os.getenv("MENU_NAME")
        self.site_name = os.getenv("SITE_NAME")
        self.api_password = os.getenv("API_PASSWORD")
        self.api_username = os.getenv("API_USERNAME")
        self.tenant = "tf" #FIXME: Change to env variable?
        self.token = ""
        # simple per-process rate limiter: requests per second (default 3 req/sec)
        try:
            rl_rate = float(os.getenv("RATE_LIMIT", "3"))
        except Exception:
            rl_rate = 3.0
        self.rate_limiter = SimpleRateLimiter(rate=rl_rate, per_seconds=1.0)

        # logger per-instance; enable debug if API_DEBUG env var set
        self.logger = logging.getLogger('dagsenAPI2.APIClient')
        self._metrics_enabled = os.getenv('API_DEBUG', '0').lower() in ('1', 'true', 'yes')
        if self._metrics_enabled:
            self.logger.setLevel(logging.DEBUG)
            if not self.logger.handlers:
                h = logging.StreamHandler()
                h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                self.logger.addHandler(h)

        # cache ttl (seconds) for menus; default 60 seconds (1 minute)
        try:
            self.cache_ttl = int(os.getenv("MENU_CACHE_TTL_SECONDS", "60"))
        except Exception:
            self.cache_ttl = 60

        # local in-process cache
        self._local_cache: Dict[str, Any] = {}
        self._local_cache_lock = threading.Lock()
        # per-key locks to avoid thundering herd across threads in this process
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()
        # Simple in-process metrics for debugging (only enabled when API_DEBUG)
        if self._metrics_enabled:
            self._metrics = {
                'upstream_fetch_count': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'token_refreshes': 0,
                'upstream_429s': 0,
            }
        else:
            self._metrics = None


    def get_new_token(self):
        ''' Get and set a new token for the api '''
        url = f"{self.api_base_url}/login"
        body = \
        {
            "tenant": self.tenant,
            "publicApiUserName": self.api_username,
            "password": self.api_password
        }

        try:
            response = requests.post(url, json=body)
            try:
                token = response.json().get("token")
            except Exception:
                token = None
            if token and self._metrics_enabled and self._metrics is not None:
                try:
                    self._metrics['token_refreshes'] += 1
                except Exception:
                    pass
            return token
        except:
            raise Exception("Error getting new token")
    

    def make_request(self, endpoint, retry=True):
            """
            Main function for making a request, handles token refreshment.
            Parameters:
            endpoint: str - the endpoint to call
            retry: bool - whether to retry the request (used once on failed 403)
            Returns:
            json response from the api
            """
            url = f"{self.api_base_url}/{endpoint}"
            headers = {"authorization": self.token}

            max_attempts = 3
            attempt = 0
            response = None

            def _parse_retry_after(header_val):
                if not header_val:
                    return None
                header_val = header_val.strip()
                # try integer seconds
                try:
                    return int(header_val)
                except ValueError:
                    pass
                # try HTTP-date
                try:
                    dt = email_utils.parsedate_to_datetime(header_val)
                    now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.utcnow()
                    secs = (dt - now).total_seconds()
                    return max(0, int(secs))
                except Exception:
                    return None

            while attempt < max_attempts:
                attempt += 1
                try:
                    # Respect a simple per-process rate limit before calling external API
                    try:
                        t0 = time.time()
                        self.rate_limiter.acquire()
                        waited = time.time() - t0
                        if waited > 0.001:
                            self.logger.debug(f"Rate limiter wait: {waited:.3f}s for {url}")
                    except Exception:
                        # If limiter fails for any reason, proceed (fail-open)
                        pass
                    # Instrumentation: count the actual call to upstream (only if enabled)
                    if self._metrics_enabled and self._metrics is not None:
                        try:
                            self._metrics['upstream_fetch_count'] += 1
                        except Exception:
                            pass
                    # Perform the request. Avoid logging every successful call to reduce noise;
                    # only log non-2xx responses (or debug when enabled).
                    response = requests.get(url, headers=headers, timeout=5)

                    # If 403, refresh the token and retry (once)
                    if response.status_code == 403 and retry:
                        self.logger.info("Token expired. Attempting to refresh token...")
                        self.token = self.get_new_token()
                        return self.make_request(endpoint=endpoint, retry=False)
                    elif response.status_code == 403 and not retry:
                        raise PermissionError(f"Access forbidden / 403 even after refreshing token")

                    # Handle 429 - respect Retry-After if present, else exponential backoff with jitter
                    if response.status_code == 429:
                        # Track and log rate-limited responses so we can debug upstream throttling.
                        if self._metrics_enabled and self._metrics is not None:
                            try:
                                self._metrics['upstream_429s'] += 1
                            except Exception:
                                pass
                        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                        backoff = 2 ** (attempt - 1)
                        jitter = random.uniform(0, 1)
                        wait = (retry_after if retry_after is not None else backoff) + jitter
                        self.logger.warning(f"Upstream returned 429 for {url} (attempt {attempt}) retry-after={retry_after} wait={wait:.2f}s")
                        if attempt < max_attempts:
                            time.sleep(wait)
                            continue
                        else:
                            self.logger.warning(f"Exceeded retries after 429 for {url}")
                            return None

                    try:
                        parsed = response.json()
                        # Only debug-log successful responses when debug logging is enabled
                        if self.logger.isEnabledFor(logging.DEBUG):
                            try:
                                self.logger.debug(f"Upstream response {response.status_code} for {url}")
                            except Exception:
                                pass
                        return parsed
                    except ValueError as ve:
                        # Upstream returned empty or non-JSON body; log for diagnostics and
                        # return None so callers can handle the missing data.
                        try:
                            resp_text = response.text if response is not None else ''
                        except Exception:
                            resp_text = ''
                        self.logger.error(f"API request failed: {ve} status: {response.status_code if response else 'no response'} response_text: {resp_text[:200]}")
                        return None

                except requests.RequestException as e:
                    # on network error, retry up to max_attempts
                    if attempt < max_attempts:
                        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 1))
                        continue
                    self.logger.error(f"API request failed: {e} status: {response.status_code if response else 'no response'}")
                    return None
                except PermissionError as pe:
                    self.logger.error(f"API request failed: {pe} status: {response.status_code if response else 'no response'}")
                    return None
            return None
    
    # --- caching helpers (redis preferred, local fallback) ---
    def _cache_get(self, key: str):
        with self._local_cache_lock:
            item = self._local_cache.get(key)
            if not item:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                try:
                    del self._local_cache[key]
                except KeyError:
                    pass
                return None
            return value

    def _cache_set(self, key: str, value: Any, ttl: int = 60):
        with self._local_cache_lock:
            self._local_cache[key] = (time.time() + int(ttl), value)

    def _acquire_lock(self, lock_key: str, lock_ttl: int = 30) -> bool:
        # Use per-key lock in-process to avoid multiple threads fetching the same key
        with self._locks_lock:
            lock = self._locks.get(lock_key)
            if lock is None:
                lock = threading.Lock()
                self._locks[lock_key] = lock
        # Try to acquire non-blocking
        try:
            return lock.acquire(blocking=False)
        except Exception:
            return False

    def _release_lock(self, lock_key: str):
        # Release in-process per-key lock
        with self._locks_lock:
            lock = self._locks.get(lock_key)
        if lock:
            try:
                if lock.locked():
                    lock.release()
            except RuntimeError:
                pass
            

    def fetch_menu(self, date: str, language: str) -> Dict[str, Any] : 
        """ Fetches the menu for one day from the api and returns Dictionary with the menu 
            like in menu_to_json
        Parameters
        Dates - Comma separated list of dates in format YYYY-MM-DD
        Returns
        """
        # Ensure date is a string; fall back to today if missing
        if not date:
            date = datetime.date.today().isoformat()
        endpoint = f"public/publicmenu/dates/{self.site_name}?dates={date}&menu={self.menu_name}"

        cache_key = f"menu:{self.site_name}:{date}:{language}"

        # Try cache first
        cached = self._cache_get(cache_key)
        if cached is not None:
            self.logger.debug(f"Cache hit for {cache_key}")
            if self._metrics_enabled and self._metrics is not None:
                try:
                    self._metrics['cache_hits'] += 1
                except Exception:
                    pass
            return cached
        else:
            self.logger.debug(f"Cache miss for {cache_key}")
            if self._metrics_enabled and self._metrics is not None:
                try:
                    self._metrics['cache_misses'] += 1
                except Exception:
                    pass

        # attempt to acquire a distributed lock so only one process fetches at a time
        lock_key = cache_key + ":lock"
        lock_ttl = max(10, int(self.cache_ttl))  # lock for at least cache ttl or 10s

        got_lock = self._acquire_lock(lock_key, lock_ttl)
        if got_lock:
            self.logger.debug(f"Acquired lock for {lock_key}")
            try:
                response = self.make_request(endpoint=endpoint)
                self.logger.debug(f"Raw API response for {date} ({language}): {response}")
                if not response:
                    # don't cache negative responses; return an empty menu structure
                    self.logger.debug(f"Upstream returned no data for {endpoint}")
                    return self.menu_to_json(menu_list=[], language=language, date=date)
                result = self.menu_to_json(menu_list=response, language=language, date=date)
                # cache parsed menu (store a deep copy to avoid callers mutating the cached object)
                try:
                    self._cache_set(cache_key, copy.deepcopy(result), ttl=self.cache_ttl)
                except Exception:
                    # Fallback: store the original if deepcopy fails for some reason
                    self._cache_set(cache_key, result, ttl=self.cache_ttl)
                return result
            finally:
                try:
                    self._release_lock(lock_key)
                except Exception:
                    pass
        else:
            self.logger.debug(f"Another process is fetching {cache_key}; waiting for cache")
            # another process is fetching; wait briefly for cache to appear
            wait_until = time.time() + 10
            while time.time() < wait_until:
                time.sleep(0.5)
                cached = self._cache_get(cache_key)
                if cached is not None:
                    self.logger.debug(f"Cache filled for {cache_key} while waiting")
                    return cached
            # timed out waiting; fallback to empty menu
            self.logger.debug(f"Timed out waiting for cache for {cache_key}; returning empty menu")
            return self.menu_to_json(menu_list=[], language=language, date=date)

        # Unreachable
        
    

    def menu_to_json(self, menu_list, language: str, date: str) -> Dict:
        ''' For parsing the menu fetched from poweresta and returning a json dictionary
        Parameters
        menu_list     - list of menu items
        language: str - language (sv, en, fi)
        date:     str - date in format YYYY-MM-DD
        Returns
        {
            "day": "2021-09-01",
            "dayName": "Wednesday",
            "Option 1": "Dish 1 (Allergens listed)",
            "Extra": "No menu available"    // If no menu available
        }
        '''
        language = language.lower()

        language_aliases = {
            'sv': 'sv',
            'swe': 'sv',
            'en': 'en',
            'fi': 'fi',
            'fin': 'fi'
        }

        if(language not in language_aliases):
            language = 'en' # Default to english if language not supported
        else:
            language = language_aliases[language]

        obj = {}
        obj["day"] = date
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        obj["dayName"] = days[language][date.isoweekday()]
        
        if not menu_list or len(menu_list) == 0:
            obj["Extra"] = "No menu available" 
        else: 
            i=1 # Tracks number of unnamed meal options
            menu = menu_list[0] # Here we are only interested in the one (first) day
            options = menu.get("mealOptions")
            if options is not None:
                # For every meal option
                for meal_option in menu.get("mealOptions"):
                    # Getting allergens
                    diet_text = ""
                    for diet in meal_option.get("rows")[0].get("diets", []):
                        if diet.get("language") == language:
                            diets = diet.get("dietShorts", [])
                            diet_text = f""" ({", ".join(diets)})""" if diets else ""
                    # Getting option and dish names
                    option_name = f"Unnamed meal option {i}"
                    for name_entry in meal_option.get("names", []):
                        if name_entry.get("language") == language:
                            option_name = name_entry.get("name", f"Unnamed meal option {i}")
                            i = i + 1
                            break
                    dish_name = "None"
                    for name_row in meal_option.get("rows")[0].get("names"):
                        if name_row.get("language") == language:
                            dish_name = name_row.get("name", "Unnamed dish")
                            # Add allergens
                            dish_name += diet_text
                    obj[option_name] = dish_name
        return obj


    def next_meal_date(self, days):
        ''' Returns the next date when a meal is served, skipping saturdays & sundays.'''
        date = datetime.date.today()
        d = int(days)

        for i in range(0, d):
            date = date + datetime.timedelta(days=1)
            while (date.isoweekday() > 5):
              date = date + datetime.timedelta(days=1) 

        return date.isoformat()
    

    def json_menu(self, date, language) -> Dict:
        ''' Returns json object with menu for a given date '''
        return self.fetch_menu(date=date, language=language)


    def textAndMeals(self, date, language):
        ''' Returns menu for a given date in text format '''
        menu = self.fetch_menu(date=date, language=language)
        if not isinstance(menu, dict):
            # Log the unexpected payload for diagnostics and return a friendly message
            try:
                self.logger.error(f"textAndMeals: unexpected menu payload for date={date}, language={language}: {menu!r}")
            except Exception:
                pass
            return Response("No menu available", mimetype='text/plain; charset=utf-8')

        # Work on a shallow copy to avoid mutating the cached object
        safe_menu = dict(menu)
        safe_menu.pop("day", None)
        safe_menu.pop("dayName", None)

        output = ""
        if len(safe_menu) == 0:
            output = "No menu available"
        else:
            for key, value in safe_menu.items():
                output += f"{key}: {value}\r\n"
        return Response(output, mimetype='text/plain; charset=utf-8')
    

