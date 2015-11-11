"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

import flask

app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)

if __name__ == '__main__':
    app.run()
