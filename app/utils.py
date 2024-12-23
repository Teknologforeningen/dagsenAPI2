import requests
import os
import datetime
from dotenv import load_dotenv


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
        self.tenant = "tf" #TODO: Change to env variable
        self.token = ""
        print(self.menu_name)

    # For refreshing CWT token when it expires
    def get_new_token(self):
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
    
    # This is a main function for making a request. More specific request methods use this.
    # Why? 
    # To handle things like token refreshment.
    def make_request(self, endpoint, data=None, retry=True):
            url = f"{self.api_base_url}/{endpoint}"
            headers = {
                "authorization": self.token
            }

            try:
                print(f"Request made to {url}, with header:{headers}")
                response = requests.get(url, headers=headers)

                # If 403, refresh the token and retry (once)
                if response.status_code == 403 and retry:
                    print("Token expired. Attempting to refresh token...")
                    self.token = self.get_new_token()
                    print(f"generated new roken: {self.token}")
                    return self.make_request(endpoint=endpoint, data=None, retry=False)

                elif response.status_code == 403 and not retry:
                    print("Refreshing token did not help - response still 403...") #TODO: make better error handling
                    raise PermissionError(f"Access forbidden / 403 even after refreshing token")

                # Raise for other errors
                return response.json()

            except requests.RequestException as e:
                print(f"API request failed: {e} status: {response.status_code}") #TODO: change to return error instead of printing
                return None
            except PermissionError as pe:
                print(f"API request failed: {pe} status: {response.status_code}") #TODO: change to return error instead of printing
                return None
            

    # Date format: Comma separated list of dates in format YYYY-MM-DD.
    def fetch_menu(self):
        # Current day
        today = datetime.date.today().isoformat()

        endpoint = f"public/publicmenu/dates/{self.site_name}?dates={today}&menu={self.menu_name}"

        # Define headers, including the authorization key

        try:
            response = self.make_request(endpoint=endpoint)
            return response
        except requests.exceptions.RequestException as e:
            return {'error': f"{str(e)}  actual response was {response}"}
        except AttributeError as Ae:
            return {'error': f" AttributeError with details: {Ae}, and endpoint={endpoint}"}

    # For parsing the resulting menu and getting the relevant data
    def parse_menu(rawmenu):
        if not rawmenu:
            return {'error': 'No menu data found'}
        try:
            return [
                {
                    'name': item['name'],
                    'price': item['price'],
                    'description': item['description']
                }
                for item in rawmenu
            ]
        except KeyError as e:
            print(f"Error parsing data: Missing key {e}")
            return []
