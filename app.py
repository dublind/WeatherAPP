#meaking the weather app

from flask import Flask
from markupsafe import escape
from flask import url_for

app = Flask(__name__)

@app.route('/')
def Weather():
    return 'Hello this it is the weather app of chile'



