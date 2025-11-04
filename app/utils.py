import requests
import os
import datetime
from dotenv import load_dotenv
from flask import Response, request, render_template
from typing import Dict, List, Any
import json
import time
import random
import email.utils as email_utils
import threading

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
            return response.json().get("token")
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
                        self.rate_limiter.acquire()
                    except Exception:
                        # If limiter fails for any reason, proceed (fail-open)
                        pass
                    response = requests.get(url, headers=headers, timeout=5)

                    # If 403, refresh the token and retry (once)
                    if response.status_code == 403 and retry:
                        print("Token expired. Attempting to refresh token...")
                        self.token = self.get_new_token()
                        return self.make_request(endpoint=endpoint, retry=False)
                    elif response.status_code == 403 and not retry:
                        raise PermissionError(f"Access forbidden / 403 even after refreshing token")

                    # Handle 429 - respect Retry-After if present, else exponential backoff with jitter
                    if response.status_code == 429:
                        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                        backoff = 2 ** (attempt - 1)
                        jitter = random.uniform(0, 1)
                        wait = (retry_after if retry_after is not None else backoff) + jitter
                        if attempt < max_attempts:
                            time.sleep(wait)
                            continue
                        else:
                            print(f"Exceeded retries after 429 for {url}")
                            return None

                    return response.json()

                except requests.RequestException as e:
                    # on network error, retry up to max_attempts
                    if attempt < max_attempts:
                        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 1))
                        continue
                    print(f"API request failed: {e} status: {response.status_code if response else 'no response'}") #FIXME: logging instead of printing
                    return None
                except PermissionError as pe:
                    print(f"API request failed: {pe} status: {response.status_code if response else 'no response'}") #FIXME: logging instead of printing
                    return None
            return None
            

    def fetch_menu(self, date: str, language: str) -> Dict[str, Any] : 
        """ Fetches the menu for one day from the api and returns Dictionary with the menu 
            like in menu_to_json
        Parameters
        Dates - Comma separated list of dates in format YYYY-MM-DD
        Returns
        """
        endpoint = f"public/publicmenu/dates/{self.site_name}?dates={date}&menu={self.menu_name}"

        try:
            response = self.make_request(endpoint=endpoint)
            return self.menu_to_json(menu_list=response, language=language, date=date)
        except requests.exceptions.RequestException as e:
            return {'error': f"{str(e)}  actual response was {response}"}
        except AttributeError as Ae:
            return {'error': f" AttributeError with details: {Ae}, and endpoint={endpoint}"}
    

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
        del menu["day"]
        del menu["dayName"]
        output = ""
        if len(menu) == 0:
            output = "No menu available"
        else:
            for key, value in menu.items():
                output += f"{key}: {value}\r\n"
        return Response(output, mimetype='text/plain; charset=utf-8')
    

