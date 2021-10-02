from datetime import datetime
from typing import Dict
from urllib.parse import parse_qs

import socketio
from random import random, randint, choice
from aiohttp import web


from engine.vector import Vector
from engine.PlanetObject import PlanetObject
from engine.util import validNick
from engine.Config import ConfigData
from engine.ObjectManager import ObjectManager

# Set up Web Server
from src.server.engine.PlayerInfo import PlayerInfo
from src.server.engine.TankObject import TankObject

app = web.Application()
sio = socketio.AsyncServer(async_mode='aiohttp')
sio.attach(app)

object_manager = ObjectManager()
users = object_manager.users
sockets = object_manager.sockets
# for _ in range(1):
#     object_manager.create_planet(
#         position=Vector(ConfigData.gameWidth / 2 + 500 * random(), ConfigData.gameHeight / 2 + 500 * random()),
#         radius=randint(500, 1000))

object_manager.load_level_file('./levels/Stage 1/Triplets.txt')


@sio.event
async def connect(sid, socket, auth):
    socket_parse = parse_qs(socket['QUERY_STRING'])
    session_type = socket_parse['type'][0]
    print('A user connected!', session_type)
    async with sio.session(sid) as session:
        session['type'] = session_type
        session['currentPlayer'] = PlayerInfo(
            id=sid,
            w=0,
            h=0,
            hue=round(random() * 360),
            type=session['type'],
            lastHeartbeat=datetime.now().timestamp(),  # 'lastHeartbeat': new Date().getTime(),
            target=Vector(0, 0)
        )

@sio.event
async def disconnect(sid):
    print('A user disconnected!', sid)
    object_manager.remove_player(sid)
    # TODO: Alert other users that sid has disconnected and to remove their sprite


@sio.event
async def gotit(sid, player):
    player = PlayerInfo.from_dict(player, object_manager.tanks)
    print('[INFO] Player ' + player.name + ' connecting!')

    if player.id in users:
        print('[INFO] Player ID is already connected, kicking.')
        await sio.disconnect(sid)
    elif not validNick(player.name):
        await sio.emit('kick', 'Invalid username.')
        await sio.disconnect(sid)

    else:
        async with sio.session(sid) as session:
            print('[INFO] Player ' + player.name + ' connected!')
            sockets[player.id] = sid
            session['currentPlayer'] = player
            session['currentPlayer'].lastHeartbeat = datetime.now().timestamp()
            object_manager.create_tank(longitude=random() * 360,
                                       home_planet=choice(list(object_manager.planets.values())),
                                       sid=sid,
                                       color=str(int(random() * 360)))
            # tanks[sid] = TankObject(longitude=random() * 360,
            #                         planet=choice(list(planets.values())),
            #                         color=str(int(random() * 360))
            #                         )

            users.append(session['currentPlayer'])

            await sio.emit('playerJoin', {'name': session['currentPlayer'].name})

            await sio.emit('gameSetup',
                           {'gameWidth': 1024,  # c.gameWidth,
                            'gameHeight': 1024,  # c.gameHeight
                            },
                           room=sid)


@sio.event
async def respawn(sid):
    await send_objects_initial(room=sid)
    async with sio.session(sid) as session:
        if session['currentPlayer'].id in users:
            users.remove(session['currentPlayer'].id)
        await sio.emit('welcome', session['currentPlayer'].to_json(), room=sid)
        print('[INFO] User ' + session['currentPlayer'].name + ' respawned!')


@sio.event
async def pingcheck(sid):
    # socket.emit('pongcheck');
    print(f'{sid} is pingchecking.')
    await sio.emit('pongcheck', room=sid)

@sio.event
async def playerChat(sid, data):
    # TODO: Regex replace
    _sender = data['sender'].replace('/(<([^>]+)>)/ig', '')
    _message = data['message'].replace('/(<([^>]+)>)/ig', '')
    now: datetime = datetime.now()
    if ConfigData.logChat == 1:
        print(f'[CHAT] [{now.hour:02d}:{now.minute:02d}] {_sender}: {_message}')
    await sio.emit('serverSendPlayerChat', {'sender': _sender, 'message': _message[:35]}, skip_sid=sid)


@sio.event
async def kick(sid, data):
    async with sio.session(sid) as session:
        if session['currentPlayer'].admin:
            reason = ''
            worked = False
            for e in range(len(users)):
                if users[e].name == data[0] and not users[e].admin and not worked:
                    if len(data) > 1:
                        for f in range(1, len(data)):
                            reason += data[f] if f == data.length else f'{data[f]} '
                    if reason != '':
                        print('[ADMIN] User ' + users[e].name + ' kicked successfully by ' + session[
                            'currentPlayer'].name + ' for reason ' + reason)
                    else:
                        print('[ADMIN] User ' + users[e].name + ' kicked successfully by ' + session[
                            'currentPlayer'].name)
                    await sio.emit('serverMSG', f'User {users[e].name} was kicked by {session["currentPlayer"].name}',
                                   room=sid)
                    await sio.emit('kick', reason, room=sockets[users[e].id])
                    await sio.disconnect(sid=sockets[users[e].id])
                    users.pop(e)
                    worked = True
            if not worked:
                await sio.emit('serverMSG', 'Could not locate user or user is an admin.', room=sid)
        else:
            print(f'[ADMIN] {session["currentPlayer"]} is trying to use -kick but isn\'t an admin.')
            await sio.emit('serverMSG', 'You are not permitted to use this command.', room=sid)


@sio.on('0')
async def heartbeat(sid, target):
    async with sio.session(sid) as session:
        session["currentPlayer"].lastHeartbeat = datetime.now().timestamp()
        if target['x'] != session["currentPlayer"].x or target['y'] != session["currentPlayer"].y:
            session["currentPlayer"].target = Vector(**target)

@sio.event
async def strafe_left(sid):
    # print(f'{sid} is moving left')
    object_manager.strafe_left(sid)

@sio.event
async def strafe_right(sid):
    # print(f'{sid} is moving right')
    object_manager.strafe_right(sid)

@sio.event
async def angle_left(sid):
    object_manager.angle_left(sid)

@sio.event
async def angle_right(sid):
    object_manager.angle_right(sid)

@sio.event
async def fire_gun(sid):
    object_manager.fire_gun_sid(sid)

@sio.event
async def power_up(sid):
    object_manager.power_up(sid)
@sio.event
async def power_down(sid):
    object_manager.power_down(sid)
@sio.event
async def next_bullet(sid):
    object_manager.next_bullet(sid)

async def send_objects_initial(*args, **kwargs):
    return await object_manager.send_objects_initial(sio, *args, **kwargs)


async def send_updates(*args, **kwargs):
    # await sio.emit('serverTellPlayerMove', [visibleCells, visibleFood, visibleMass, visibleVirus], room=sid)
    return await object_manager.send_updates(sio, *args, **kwargs)


async def tickPlayer(currentPlayer):
    if currentPlayer.lastHeartbeat < datetime.now().timestamp() - ConfigData.maxHeartbeatInterval:
        sid = sockets[currentPlayer.id]
        await sio.emit('kick', f'Last heartbeat received over {ConfigData.maxHeartbeatInterval} ago.', room=sid)
        await sio.disconnect(sid)

    # movePlayer(currentPlayer)


async def moveloop():
    return await object_manager.move(sio)


async def gameloop():
    pass


# Web server logic
async def index(request):
    with open('../client/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


async def favicon(request):
    # with open('../client/favicon.ico') as f:
    #     return web.Response(text=f.read())
    return web.FileResponse('../client/favicon.ico')


def setInterval(func, timeout):
    async def wrapper(func, timeout):
        while True:
            await func()
            await sio.sleep(timeout / 1000)

    sio.start_background_task(wrapper, *(func, timeout))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # Add the static files
    app.router.add_get('/', index)
    app.router.add_get('/favicon.ico', favicon)
    app.router.add_static('/css', '../client/css')
    app.router.add_static('/img', '../client/img')
    app.router.add_static('/audio', '../client/audio')
    app.router.add_static('/js', '../client/js')

    # Initialize the loops
    sio.start_background_task(send_objects_initial)
    setInterval(moveloop, 1000 / 60)
    setInterval(gameloop, 1000)
    setInterval(send_updates, 1000 / ConfigData.networkUpdateFactor)

    # Run the web server
    web.run_app(app)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
