import re


def validNick(nickname):
    regex = '^\w*$'
    return bool(re.search(regex, nickname))