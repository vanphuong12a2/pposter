# -*- coding: utf-8 -*-

from datetime import datetime
from validate_email import validate_email
import re
from lepl.apps.rfc3696 import HttpUrl
from BeautifulSoup import BeautifulSoup
import urllib
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


class MyException(Exception):
    pass


def is_valid_email(email):
    return validate_email(email)


def is_allowed_file(filename, exts):
    return '.' in filename and filename.rsplit('.', 1)[1] in exts


def format_datetime(timestamp):
    """Format a timestamp for display."""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d @ %H:%M')


def is_strong_pass(password):
    """
    Verify the strength of 'password'
    Returns a dict indicating the wrong criteria
    A password is considered strong if:
        8 characters length or more
        1 digit or more
        1 symbol or more
        1 uppercase letter or more
        1 lowercase letter or more
    """
    # calculating the length
    length_error = len(password) < 8

    # searching for digits
    digit_error = re.search(r"\d", password) is None

    # searching for uppercase
    uppercase_error = re.search(r"[A-Z]", password) is None

    # searching for lowercase
    lowercase_error = re.search(r"[a-z]", password) is None

    # searching for symbols
    symbol_error = re.search(r"[ !#$@%&'()*+,-./[\\\]^_`{|}~" + r'"]', password) is None

    # overall result
    password_ok = not (length_error or digit_error or uppercase_error or lowercase_error or symbol_error)

    return password_ok


def is_url(string):
    validator = HttpUrl()
    return validator(string)


def get_url_info(url):
    try:
        page = urllib.urlopen(url).read()
    except:
        raise MyException("error")
    soup3 = BeautifulSoup(page)
    desc = soup3.findAll(attrs={"name": "description"})
    return soup3.title.string.encode('utf-8'), desc[0]['content'].encode('utf-8')
