from flask import Blueprint, render_template
from .utils import APIClient
import datetime

client = APIClient()

# Create a blueprint
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return "Welcome to the home page!"

@main.route('/taffa/<language>/today/') #FIXME: should return text menu for todays date
def todaysMenuText(language):
    todaysDate = datetime.date.today().isoformat()
    return client.textAndMeals(language=language, date=todaysDate)

@main.route('/taffa/<language>/json/<int:days>/') #Needed for info
def jsonNextMeal(language, days):
  date = client.next_meal_date(days)
  return client.json_menu(language=language, date=date)

@main.route('/taffa/<language>/<int:days>/')
def menuText(language, days):
    date = client.next_meal_date(days)
    return client.textAndMeals(language=language, date=date)



@main.route('/taffa/<language>/html/today/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/today/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/week/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/week/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/txt/<day>/<month>/<year>/') #FIXME: which of these are needed?

 #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/<day>/<month>/<year>/') #FIXME: which of these are needed?







@main.route('/taffa/<language>/html/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/<int:days>/') #FIXME: which of these are needed?

# Explicit error handlers
@main.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500