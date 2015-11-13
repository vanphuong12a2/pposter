#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

import os
from flask import Flask, g, url_for, render_template, request, redirect, flash, session
import redis
import time
from oauth2client.client import flow_from_clientsecrets
import httplib2
from apiclient.discovery import build
from werkzeug import secure_filename
import boto3
import json
from flask_jsglue import JSGlue
from common import allowed_file
from redis_model import RedisModel


jsglue = JSGlue()
app = Flask(__name__)
jsglue.init_app(app)
app.config.from_object('config')
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)


r = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=app.config['REDIS_DB'])
if app.config['TEST']:
    conn = None
else:
    conn = boto3.resource('s3')
model = RedisModel(r, conn, app.config)


@app.before_request
def before_request():
    g.test = app.config['TEST']


@app.route('/')
def do_nothing():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('timeline'))
    else:
        return render_template('layout.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if (app.config['USERNAME'], app.config['PASSWORD']) == (request.form['username'], request.form['password']):
            session['logged_in'] = True
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            error = "Wrong user!"
    return render_template('login.html', error=error)


@app.route('/google_auth')
def google_auth():
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)


@app.route('/auth_return', methods=['GET'])
def auth_return():
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    if 'code' in request.args:
        code = request.args.get('code')
        credentials = flow.step2_exchange(code)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('plus', 'v1', http=http)
        user_info = service.people().get(userId='me').execute()
        if user_info['id'] == app.config['GOOGLE_ID']:
            session['logged_in'] = True
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            return render_template('layout.html', error='Wrong user!')
    else:
        return render_template('layout.html', error='Authentication failed, please log in again!')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out!')
    return redirect(url_for('do_nothing'))


@app.route('/timeline')
def timeline():
    tweets = model.get_tweets(0)
    return render_template('timeline.html', tweets=tweets)


@app.route('/timelinejson', methods=['GET'])
def timelinejson():
    if 'offset' in request.args:
        offset = int(request.args['offset'])
        tweets = model.get_tweets(offset)
        return json.dumps(tweets)
    else:
        return "No offset!"


@app.route('/add_tweet', methods=['POST'])
def add_tweet():
    error = None
    if request.method == 'POST':
        #Get tweet
        tweet_content = request.form['tweet']
        if len(tweet_content) not in range(app.config['TWEET_MIN_LEN'], app.config['TWEET_MAX_LEN'] + 1):
            error = "Tweet length error!"
        tweet_file = request.files['img']
        if tweet_file and not allowed_file(tweet_file.filename, app.config['ALLOWED_EXTENSIONS']):
            error = "File ext not supported!"

        if error is not None:
            #TODO: tmp, no tweet appears here
            return render_template("timeline.html", error=error)

        new_imgname = None
        if tweet_file:
            org_imgname = secure_filename(tweet_file.filename)
            new_imgname = "tweet" + str(model.get_new_tweet_id()) + '.' + org_imgname.rsplit('.', 1)[1]
            if app.config['TEST']:
                tweet_file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_imgname))
            else:
                model.s3_put(conn, app.config['BUCKET'], new_imgname, tweet_file)
        model.add_tweet(tweet_content, time.time(), 'user', new_imgname)
        return redirect(url_for('timeline'))

if __name__ == '__main__':
    if app.config['TEST']:
        app.run(debug=app.config['DEBUG'])
    else:
        app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
