from flask import Blueprint, render_template, Response
from .utils import APIClient
import datetime
import json

client = APIClient()

# Create a blueprint
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('index.html')

# Todays menu in text format
@main.route('/taffa/<language>/today/')
def todaysMenuText(language):
    todaysDate = datetime.date.today().isoformat()
    return client.textAndMeals(language=language, date=todaysDate)

# Menu in x days in text format
@main.route('/taffa/<language>/<int:days>/')
def menuText(language, days):
    date = client.next_meal_date(days)
    return client.textAndMeals(language=language, date=date)

# Weekly menu in text format
@main.route('/taffa/<language>/week/')
def weeklyMenuText(language):
    days = []
    for i in range(0, 5):
        date = client.next_meal_date(i)
        days.append(client.textAndMeals(language=language, date=date))
    return "\n".join(days)


# Todays menu in json format
@main.route('/taffa/<language>/json/today/')
def jsonTodaysMenu(language):
    todaysDate = datetime.date.today().isoformat()
    menu = client.json_menu(language=language, date=todaysDate)
    return Response(json.dumps(menu, ensure_ascii=False), mimetype='application/json; charset:utf-8')

# Menu in x days in json format
@main.route('/taffa/<language>/json/<int:days>/') #Needed for info
def jsonNextMeal(language, days):
  date = client.next_meal_date(days)
  menu = client.json_menu(language=language, date=date)
  return Response(json.dumps(menu, ensure_ascii=False), mimetype='application/json; charset:utf-8')


# Weekly menu in json format 
@main.route('/taffa/<language>/json/week/')
def jsonThisWeek(language):
    days = []
    for i in range(0, 5):
        date = client.next_meal_date(i)
        days.append(client.json_menu(language=language, date=date))
    return Response(json.dumps(days, ensure_ascii=False), mimetype='application/json; charset:utf-8')


# Todays menu in html format
@main.route('/taffa/<language>/html/today/') #FIXME: which of these are needed?
def todaysMenuHTML(language):
    days = []
    todaysDate = datetime.date.today().isoformat()
    days.append(client.json_menu(date=todaysDate, language=language))
    print(client.json_menu(date=todaysDate, language=language))
    return render_template('menu.html', days=days)

# Menu in x days in html format
@main.route('/taffa/<language>/html/<int:days>/')
def menuHTML(language, days):
    date = client.next_meal_date(days)
    return render_template('menu.html', days=[client.json_menu(language=language, date=date)])

# Weekly menu in html format
@main.route('/taffa/<language>/html/week/')
def htmlThisWeek(language):
    days = []
    for i in range(0, 5):
        date = client.next_meal_date(i)
        days.append(client.json_menu(language=language, date=date))
    return render_template('menu.html', days=days)


@main.route('/taffa/<language>/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/txt/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/json/<day>/<month>/<year>/') #FIXME: which of these are needed?

@main.route('/taffa/<language>/html/<day>/<month>/<year>/') #FIXME: which of these are needed?



# Explicit error handlers
@main.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500