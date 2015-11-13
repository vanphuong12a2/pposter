#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

import os
from flask import Flask, g, url_for, render_template, request, redirect, flash, session, abort
import redis
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
    g.curr_user = None
    if 'user_id' in session:
        g.curr_user = {'name': model.get_username(session['user_id']), 'link': model.get_userlink(session['user_id'])}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        if model.is_valid_user(request.form['email'], request.form['password']):
            session['user_id'] = request.form['email']
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            error = "Wrong user!"
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        if not request.form['email'] or '@' not in request.form['email']:
            error = 'You have to enter an valid email'
        elif model.is_registered(request.form['email']):
            error = 'This email was registered'
        elif not request.form['name']:
            error = 'You have to enter your name'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        else:
            model.add_user(request.form['email'], request.form['name'], request.form['password'])
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error)


@app.route('/google_auth')
def google_auth():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile email', redirect_uri=url_for('auth_return', _external=True))
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)


@app.route('/auth_return', methods=['GET'])
def auth_return():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    if 'code' in request.args:
        code = request.args.get('code')
        credentials = flow.step2_exchange(code)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('plus', 'v1', http=http)
        user_info = service.people().get(userId='me').execute()
        print user_info
        if user_info['id'] == app.config['GOOGLE_ID']:
            session['user_id'] = user_info['emails'][0]['value']  # Need to be checked
            model.add_user(session['user_id'], user_info['name']['givenName'])
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            return render_template('layout.html', error='Wrong user!')
    else:
        return render_template('layout.html', error='Authentication failed, please log in again!')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You were logged out!')
    return redirect(url_for('timeline'))


@app.route('/', methods=['GET'])
def timeline():
    if g.curr_user is not None:
        lusers = None
        tweets = model.get_tweets(lusers=lusers, offset=0)
        return render_template('timeline.html', tweets=tweets, more_tweet=True)
    else:
        return render_template('layout.html')


@app.route('/timelinejson', methods=['GET'])
def timelinejson():
    if g.curr_user is None:
        return render_template('login.html')
    if 'offset' in request.args:
        offset = int(request.args['offset'])
        tweets = model.get_tweets(offset=offset)
        return json.dumps(tweets)
    else:
        abort(404)


@app.route('/<userlink>/timelinejson', methods=['GET'])
def user_timelinejson(userlink):
    if g.curr_user is None:
        return render_template('login.html')
    if 'offset' in request.args:
        uid = model.get_userid(userlink)
        if model.registered(uid):
            offset = int(request.args['offset'])
            tweets = model.get_tweets(lusers=[uid], offset=offset)
            return json.dumps(tweets)
        else:
            return redirect(url_for('user_timeline', userlink=g.curr_user[1]), more_tweet=True)
    else:
        abort(404)


@app.route('/<userlink>')
def user_timeline(userlink):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(userlink)
    if model.is_registered(uid):
        tweets = model.get_tweets(lusers=[uid], offset=0)
        return render_template('timeline.html', tweets=tweets, timelineowner=userlink, more_tweet=True)
    else:
        flash("There is no user with that id")
        return redirect(url_for('timeline'))


@app.route('/<userlink>/follow')
def follow(userlink):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(userlink)
    model.add_follower(session['user_id'], uid)
    return redirect(url_for('user_timeline', userlink=userlink))


@app.route('/<userlink>/unfollow')
def unfollow(userlink):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(userlink)
    model.remove_follower(session['user_id'], uid)
    return redirect(url_for('user_timeline', userlink=userlink))


@app.route('/public')
def public_timeline():
    tweets = model.get_tweets(offset=0)
    return render_template('timeline.html', tweets=tweets)


@app.route('/add_tweet', methods=['POST'])
@app.route('/<userlink>/add_tweet', methods=['POST'])
def add_tweet(userlink=None):
    if g.curr_user is None:
        return render_template('login.html')
    if userlink is not None and userlink != g.curr_user['link']:
        return "Illegal post"
    if request.method == 'POST':
        #Get tweet
        tweet_content = request.form['tweet']
        if len(tweet_content) not in range(app.config['TWEET_MIN_LEN'], app.config['TWEET_MAX_LEN'] + 1):
            return render_template("timeline.html", error="Tweet length error!")
        tweet_file = request.files['img']
        if tweet_file and not allowed_file(tweet_file.filename, app.config['ALLOWED_EXTENSIONS']):
            return render_template("timeline.html", error="File ext not supported!")

        new_imgname = None
        if tweet_file:
            org_imgname = secure_filename(tweet_file.filename)
            new_imgname = "tweet" + str(model.get_new_tweet_id()) + '.' + org_imgname.rsplit('.', 1)[1]
            if app.config['TEST']:
                tweet_file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_imgname))
            else:
                model.s3_put(conn, app.config['BUCKET'], new_imgname, tweet_file)
        model.add_tweet(tweet_content, session['user_id'], new_imgname)
        if userlink is None:
            return redirect(url_for('timeline'))
        else:
            return redirect(url_for('user_timeline', userlink=userlink))

if __name__ == '__main__':
    if app.config['TEST']:
        app.run(debug=app.config['DEBUG'])
    else:
        app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
