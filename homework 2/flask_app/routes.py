"""
routes.py — defines the URL paths (routes) that the web app responds to.

A ROUTE maps a URL to a Python function. When a browser visits a URL,
Flask calls the matching function and sends back its return value as HTML.

Example:
  Browser visits http://localhost:8080/resume
      → Flask calls the resume() function below
      → resume() queries the database and renders resume.html
      → The browser receives and displays the HTML page

The @app.route('/path') decorator is what connects a URL to a function.
You learned about decorators in your OOP course — they wrap a function
with extra behavior. Here, the decorator registers the function with Flask.

NOTE: Chat messages do NOT go through a route. They travel over a
      WebSocket connection handled in flask_app/utils/socket_events.py.
      Read that file after this one to see how the chat works.
"""

from flask import current_app as app
from flask import render_template

# db is set by create_app() in __init__.py after the app is initialized.
# It gives every route access to the database without creating a new
# connection on each request.



# ------------------------------------------------------------------
# HOME PAGE
# ------------------------------------------------------------------

@app.route('/')
def home():
    """
    Render the homepage.

    The homepage is defined in templates/home.html.
    Edit that file to add your own bio, photo, and introduction.
    """
    return render_template('home.html')


# ------------------------------------------------------------------
# RESUME PAGE
# ------------------------------------------------------------------

@app.route('/resume')
def resume():
    """
    Render the resume page with live data from the database.

    We call db.getResumeData() to load all institutions, positions,
    experiences, and skills. The result is a nested dictionary that
    we pass to the template as the variable 'resume'.

    In resume.html, Jinja2 loops over this dictionary to render the page.
    The chat panel is also part of resume.html — students can ask the AI
    questions about what they're reading.

    # NOTE: To update your resume, edit the CSV files in:
    #         flask_app/database/initial_data/
    #       Then restart the app to reload the database.
    """
    resume_data = app.db.getResumeData()
    return render_template('resume.html', resume=resume_data)
