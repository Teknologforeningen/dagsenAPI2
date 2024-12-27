from flask import Blueprint, render_template
from .utils import APIClient

client = APIClient()

# Create a blueprint
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return "Welcome to the home page!"

@main.route('/dagensmeny')
def menu():
    return client.fetch_todays_menu()

@main.route('/testmeny')
def testmenu():
    return client.fetch_test_menu()

@main.route('/taffa/<language>/today/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/today/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/today/') #FIXME: which of these are needed?


@main.route('/taffa/<language>/json/week/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/week/') #FIXME: which of these are needed?



@main.route('/taffa/<language>/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/txt/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/<int:days>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/<int:days>/') #FIXME: which of these are needed?





@main.route('/taffa/<language>/html/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/<int:days>/') #FIXME: which of these are needed?

# Explicit error handlers
@main.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500