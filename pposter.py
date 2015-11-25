#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""


# set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on available packages.
async_mode = None

if async_mode is None:
    try:
        import eventlet
        assert eventlet
        async_mode = 'eventlet'
    except ImportError:
        pass

    if async_mode is None:
        try:
            from gevent import monkey
            assert monkey
            async_mode = 'gevent'
        except ImportError:
            pass

    if async_mode is None:
        async_mode = 'threading'

    print('async_mode is ' + async_mode)

# monkey patching is necessary because this application uses a background
# thread
if async_mode == 'eventlet':
    import eventlet
    eventlet.monkey_patch()
elif async_mode == 'gevent':
    from gevent import monkey
    monkey.patch_all()


from flask import Flask, g, url_for, render_template, request, redirect, flash, session, abort
from oauth2client.client import flow_from_clientsecrets
import httplib2
import json
from apiclient.discovery import build
from flask_jsglue import JSGlue
from model.redis_model import RedisModel
import lib.common as common
from lib.mysocket import MySocket
from flask_socketio import join_room


jsglue = JSGlue()
app = Flask(__name__)
jsglue.init_app(app)
app.config.from_object('config.config')
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)

model = RedisModel(app.config)
my_socket = MySocket(app, async_mode)
socketio = my_socket.get_socketio()
#socketio = SocketIO(app, async_mode=async_mode)
thread = None


@app.before_request
def before_request():
    g.test = app.config['LOCAL']
    g.curr_user = None
    if 'user_id' in session:
        g.curr_user = {'name': model.get_username(session['user_id']), 'alias': model.get_useralias(session['user_id'])}


@socketio.on('join', namespace='/noti')
def join():
    if 'user_id' in session:
        join_room(session['user_id'])
        g.joined_room = True


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
        if not request.form['email'] or not common.is_valid_email(request.form['email']):
            error = 'You have to enter an valid email'
        elif model.is_registered(request.form['email']):
            error = 'This email was registered'
        elif not request.form['name']:
            error = 'You have to enter your name'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif not common.is_strong_pass(request.form['password']):
            error = 'The password is not strong enough'
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
        if app.config['TESTING']:
            return request.args['code']
        code = request.args.get('code')
        credentials = flow.step2_exchange(code)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('plus', 'v1', http=http)
        user_info = service.people().get(userId='me').execute()
        session['user_id'] = user_info['emails'][0]['value']
        if not model.is_registered(session['user_id']):
            model.add_user(session['user_id'], user_info['name']['givenName'])
        flash("You were logged in!")
        return redirect(url_for('timeline'))
    else:
        return render_template('layout.html', error='Authentication failed, please log in again!')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You were logged out!')
    return redirect(url_for('timeline'))


def get_noti_url(notis):
    with app.app_context():
        for noti in notis:
            if noti['noti_type'] == 'follow_noti':
                noti['noti_url'] = url_for('user_timeline', useralias=model.get_useralias(noti['noti_target']), noti=noti['noti_id'])
            else:
                noti['noti_url'] = url_for('show_tweet', tweet_id=noti['noti_target'], noti=noti['noti_id'])


@app.route('/')
def timeline():
    if g.curr_user is None:
        return render_template('login.html')
    param = {}
    for key in ['error', 'anchor']:
        param[key] = None
        if key in session:
            param[key] = session[key]
            session.pop(key)
    lusers = model.get_following_ids(session['user_id']) + [session['user_id']]
    tweets, more_tweet = model.get_tweets(lusers=lusers, offset=0, anchor=param['anchor'])
    unread_notis = model.get_unread_notis(session['user_id'])
    get_noti_url(unread_notis)
    #TODO: if request.hasgtag => filter tweet
    return render_template('timeline.html', tweets=tweets, more_tweet=more_tweet, notis=unread_notis, error=param['error'])


@app.route('/<useralias>', methods=['GET'])
def user_timeline(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    if model.is_registered(uid):
        param = {}
        for key in ['error', 'anchor']:
            param[key] = None
            if key in session:
                param[key] = session[key]
                session.pop(key)
        if 'noti' in request.args:
            model.set_read_noti(request.args['noti'])
        tweets, more_tweet = model.get_tweets(lusers=[uid], offset=0, anchor=param['anchor'])
        timelineowner = model.get_user_info(uid)
        timelineowner['followed'] = model.check_followed(session['user_id'], uid)
        unread_notis = model.get_unread_notis(session['user_id'])
        get_noti_url(unread_notis)
        return render_template('timeline.html', tweets=tweets, timelineowner=timelineowner, more_tweet=more_tweet, notis=unread_notis, error=param['error'])
    else:
        flash("There is no user with that id")
        return redirect(url_for('timeline'))


@app.route('/timelinejson', methods=['GET'])
@app.route('/<useralias>/timelinejson', methods=['GET'])
def timelinejson(useralias=None):
    if g.curr_user is None:
        return render_template('login.html')
    if 'offset' in request.args:
        offset = int(request.args['offset'])
        if useralias is None:
            lusers = model.get_following_ids(session['user_id']) + [session['user_id']]
            tweets, more_tweet = model.get_tweets(lusers=lusers, offset=offset)
        else:
            uid = model.get_userid(useralias)
            tweets, more_tweet = model.get_tweets(lusers=[uid], offset=offset)
        return json.dumps({'tweets': render_template('tweets.html', tweets=tweets), 'more_tweet': more_tweet})
    else:
        abort(404)


@app.route('/<useralias>/follow')
def follow(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    if session['user_id'] == uid:
        return redirect(url_for('timeline'))
    nid = model.add_follower(session['user_id'], uid)
    noti = model.get_noti(nid)
    get_noti_url([noti])
    tosend = json.dumps(noti)
    my_socket.noti_emit(tosend, room=uid)
    return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/<useralias>/unfollow')
def unfollow(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    if session['user_id'] == uid:
        return redirect(url_for('timeline'))
    model.remove_follower(session['user_id'], uid)
    return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/<useralias>/update_avatar', methods=['POST'])
def update_avatar(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    else:
        if useralias != g.curr_user['alias']:
            flash("Illegal access")
            return redirect(url_for('user_timeline', useralias=g.curr_user['alias']))
        new_avatar = request.files['avatar']
        model.add_user_avatar(session['user_id'], new_avatar)
        return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/<useralias>/update_info', methods=['POST'])
def update_userinfo(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    else:
        if useralias != g.curr_user['alias']:
            flash("Illegal access")
            return redirect(url_for('user_timeline', useralias=g.curr_user['alias']))
        new_name = request.form['name']
        new_alias = request.form['alias']
        if new_alias == useralias or not model.check_alias(new_alias):
            model.update_userinfo(session['user_id'], new_name, new_alias)
            return redirect(url_for('user_timeline', useralias=new_alias))
        elif new_alias[0].isdigit():
            session['error'] = "Aias should not start with digit"
            return redirect(url_for('user_timeline', useralias=useralias))
        else:
            session['error'] = "Alias was used!"
            return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/public')
def public_timeline():
    tweets, more_tweet = model.get_tweets(offset=0)
    return render_template('timeline.html', tweets=tweets, more_tweet=more_tweet)


@app.route('/public/timelinejson', methods=['GET'])
def public_timelinejson():
    if 'offset' in request.args:
        offset = int(request.args['offset'])
        tweets, more_tweet = model.get_tweets(offset=offset)
        return json.dumps({'tweets': render_template('tweets.html', tweets=tweets), 'more_tweet': more_tweet})
    else:
        abort(404)


@app.route('/add_tweet', methods=['POST'])
@app.route('/<useralias>/add_tweet', methods=['POST'])
def add_tweet(useralias=None):
    if g.curr_user is None:
        return render_template('login.html')
    if useralias is not None and useralias != g.curr_user['alias']:
        flash("Illegal access")
        return redirect(url_for('user_timeline', useralias=g.curr_user['alias']))
    error = None
    tweet_content = request.form['tweet']
    if len(tweet_content) not in range(1, app.config['TWEET_MAX_LEN'] + 1):
        error = "Tweet length error!"
    else:
        if 'img' not in request.files or not request.files['img']:
            model.add_tweet(tweet_content, session['user_id'])
        else:
            tweet_file = request.files['img']
            if not common.is_allowed_file(tweet_file.filename, app.config['ALLOWED_EXTENSIONS']):
                error = "File ext not supported!"
            else:
                model.add_tweet(tweet_content, session['user_id'], tweet_file)
    session['error'] = error
    if useralias is None:
        return redirect(url_for('timeline'))
    else:
        return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/remove_tweet', methods=['GET'])
@app.route('/<useralias>/remove_tweet')
def remove_tweet(useralias=None):
    if g.curr_user is None:
        return render_template('login.html')
    if useralias is not None and useralias != g.curr_user['alias']:
        flash("Illegal access")
        return redirect(url_for('user_timeline', useralias=g.curr_user['alias']))
    if 'tweet_id' not in request.args:
        return redirect(url_for('user_timeline', useralias=g.curr_user['alias']))
    tweet_id = request.args['tweet_id']
    if model.get_user_from_tweet(tweet_id) != session['user_id']:
        flash("Illegal access")
        return redirect(url_for('timeline'))
    next_tweet = model.remove_tweet(tweet_id)
    session['anchor'] = next_tweet
    if useralias is not None:
        return redirect(url_for('user_timeline', useralias=useralias, _anchor=next_tweet))
    return redirect(url_for('timeline', _anchor=next_tweet))


@app.route('/add_comment', methods=['POST'])
@app.route('/<useralias>/add_comment', methods=['POST'])
def add_comment(useralias=None):
    if g.curr_user is None:
        return render_template('login.html')
    error = None
    comment_content = request.form['content']
    if len(comment_content) not in range(1, app.config['TWEET_MAX_LEN'] + 1):
        error = "Comment length error"
        tweet_id = 0
    elif useralias and not model.is_registered(model.get_userid(useralias)):
        return redirect(url_for('timeline'))
    else:
        tweet_id = request.args['tweet_id']
        nid = model.add_comment(tweet_id, session['user_id'], comment_content)
        if session['user_id'] != model.get_user_from_tweet(tweet_id):
            noti = model.get_noti(nid)
            get_noti_url([noti])
            tosend = json.dumps(noti)
            my_socket.noti_emit(tosend, room=model.get_user_from_tweet(tweet_id))
    session['anchor'] = tweet_id
    session['error'] = error
    if useralias is not None:
        return redirect(url_for('user_timeline', useralias=useralias, _anchor=tweet_id))
    else:
        return redirect(url_for('timeline', _anchor=tweet_id))


@app.route('/notifications')
def notifications():
    if g.curr_user is None:
        return render_template('login.html')
    notis = model.get_all_notis(session['user_id'])
    get_noti_url(notis)
    unread_notis = model.get_unread_notis(session['user_id'])
    get_noti_url(unread_notis)
    return render_template('timeline.html', notis=unread_notis, all_notis=notis)


@app.route('/tweet<tweet_id>', methods=['GET'])
def show_tweet(tweet_id):
    if g.curr_user is None:
        return render_template('login.html')
    if 'noti' in request.args:
        model.set_read_noti(request.args['noti'])
    unread_notis = model.get_unread_notis(session['user_id'])
    get_noti_url(unread_notis)
    return render_template('timeline.html', tweets=[model.get_tweet(tweet_id)], notis=unread_notis)


@socketio.on('mark_read', namespace='/noti')
def mark_read():
    res = model.set_read_notis(session['user_id'])
    if res:
        my_socket.noti_emit('marked_noti')


if __name__ == '__main__':
    if app.config['LOCAL']:
        my_socket.get_socketio().run(app, debug=True)
        #app.run(debug=app.config['DEBUG'])
    else:
        app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
