import re


def validNick(nickname):
    regex = '^\w*$'
    return bool(re.search(regex, nickname))


# Type Aliases
# Sid is just a string representing some socket-id, which is usually some hash. Aliasing makes documentation clearer.
Sid = str

# Colors
colors = ['Red', 'Yellow', 'Blue', 'Orange', 'DarkOrange', 'Pink', 'Salmon']
