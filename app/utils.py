import requests
import os
import datetime
from dotenv import load_dotenv
from flask import Response, request, render_template
from typing import Dict, List, Any


days = {
  'sv': [' ', u'Måndag', u'Tisdag', u'Onsdag', u'Torsdag', u'Fredag', u'Lördag', u'Söndag'],
  'en': [' ', u'Monday', u'Tuesday', u'Wednesday', u'Thursday', u'Friday', u'Saturday', u'Sunday'],
  'fi': [' ', u'Maanantai', u'Tiistai', u'Keskiviikko', u'Torstai', u'Perjantai', u'Lauantai', u'Sunnuntai'],
}

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
    

    def make_request(self, endpoint, retry=True):
            """
            Main function for making a request, handles token refreshment.
            #FIXME: finish and add parameters
            """

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
                    return self.make_request(endpoint=endpoint, retry=False)

                elif response.status_code == 403 and not retry:
                    print("Refreshing token did not help - response still 403...") #TODO: make better error handling
                    raise PermissionError(f"Access forbidden / 403 even after refreshing token")

                return response.json()

            except requests.RequestException as e:
                print(f"API request failed: {e} status: {response.status_code}") #TODO: change to return error instead of printing
                return None
            except PermissionError as pe:
                print(f"API request failed: {pe} status: {response.status_code}") #TODO: change to return error instead of printing
                return None
            

    def fetch_menu(self, dates: str) -> Dict[str, Any] : 
        """ 
        Parameters
        Dates: Comma separated list of dates in format YYYY-MM-DD
        Returns
        """
        endpoint = f"public/publicmenu/dates/{self.site_name}?dates={dates}&menu={self.menu_name}"

        try:
            response = self.make_request(endpoint=endpoint)
            return response
        except requests.exceptions.RequestException as e:
            return {'error': f"{str(e)}  actual response was {response}"}
        except AttributeError as Ae:
            return {'error': f" AttributeError with details: {Ae}, and endpoint={endpoint}"}

    def fetch_todays_menu(self):
        today = datetime.date.today().isoformat()
        todays_menu = self.fetch_menu(dates=today)
        return self.menu_to_json(menuList=todays_menu, language="fi")
    
    def fetch_test_menu(self):
        dates = "2024-12-27,2024-12-28"
        test_menu = self.fetch_menu(dates=dates)
        return self.menu_to_json(menuList=test_menu, language="fi")
    

    # For parsing menu and getting the relevant data
    def menu_to_json(self, menuList: List, language: str) -> List:
        if not menuList:
            return [{'error': 'No menu data found'}]
        try:
            json_menu = []
            for menu in menuList:
                obj = {}
                # Set menu items 
                obj["day"] = menu.get("date")
                obj["dayname"] = "" #FIXME: piopulate these like old api
                obj["dayname"] = "" #FIXME: piopulate these like old api

                for meal_option in menu.get("mealOptions"):
                    

                    option_name = "None"

                    for name_entry in meal_option.get("names", []):
                        if name_entry.get("language") == language:
                            option_name = name_entry.get("name", "Unnamed meal option")
                            break
                    dish_name = "None"
                    for name_row in meal_option.get("rows")[0].get("names"):
                        if name_row.get("language") == language:
                            dish_name = name_row.get("name")
                    obj[option_name] = dish_name


        
                json_menu.append(obj)
            return json_menu
        except KeyError as e:
            return{"Error parsing data": f"Missing key {e}"}

    def nextMealDate(days):
        date = datetime.date.today()
        d = int(days)

        for i in range(0, d+1):
            datum = date + datetime.timedelta(days=1)
            while (date.isoweekday() > 5):
              date = date + datetime.timedelta(1) 

        return date