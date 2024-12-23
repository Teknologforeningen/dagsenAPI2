from flask import Blueprint
from .utils import APIClient

client = APIClient()

# Create a blueprint
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return "Welcome to the home page!"

@main.route('/about')
def about():
    return "This is the about page."

@main.route('/dagensmeny')
def menu():
    return client.fetch_menu()
