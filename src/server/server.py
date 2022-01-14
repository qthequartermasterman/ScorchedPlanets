from datetime import datetime
from multiprocessing import freeze_support

import socketio
from aiohttp import web

from engine.Config import ConfigData
from engine.RoomManager import RoomManager, RoomAlreadyExistsError
from engine.vector import Vector

# Set up Web Server
app = web.Application()
sio = socketio.AsyncServer(async_mode='aiohttp')
sio.attach(app)

# Create the Room Manager
room_manager = RoomManager(sio)
room_manager.create_room(name='test_room1', level_path='./levels/Stage 1/I Was Here First!.txt')


@sio.event
async def connect(sid, socket, auth):
    return await room_manager.connect_player(sid, socket, auth)


@sio.event
async def disconnect(sid):
    # # TODO: Alert other users that sid has disconnected and to remove their sprite
    print('A user disconnected!', sid)
    room_manager.disconnect_player(sid)


@sio.event
async def gotit(sid, player):
    await room_manager.move_player(sid=sid, new_room=player['new_room'], player_info_dict=player)


@sio.event
async def respawn(sid):
    return await room_manager.respawn(sid)


@sio.event
async def pingcheck(sid):
    print(f'{sid} is pingchecking.')
    await sio.emit('pongcheck', room=sid)


@sio.event
async def playerChat(sid, data):
    await room_manager.send_chat(sid, data)


@sio.event
async def kick(sid, data):
    # TODO: Fix the kick command!
    async with sio.session(sid) as session:
        if session['currentPlayer'].admin:
            reason = ''
            worked = False
            users = room_manager.connected_players
            for e, user in enumerate(users):
                if user.name == data[0] and not user.admin and not worked:
                    if len(data) > 1:
                        for f in range(1, len(data)):
                            reason += data[f] if f == data.length else f'{data[f]} '
                    if reason != '':
                        print('[ADMIN] User ' + user.name + ' kicked successfully by ' + session[
                            'currentPlayer'].name + ' for reason ' + reason)
                    else:
                        print('[ADMIN] User ' + user.name + ' kicked successfully by ' + session[
                            'currentPlayer'].name)
                    await sio.emit('serverMSG', f'User {user.name} was kicked by {session["currentPlayer"].name}',
                                   room=sid)
                    await sio.emit('kick', reason, room=user)
                    await sio.disconnect(sid=user)
                    # users.pop(e)  # old
                    users.pop(user)
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
            await room_manager.update_target(sid, session['currentPlayer'].target)


@sio.event
async def strafe_left(sid):
    await room_manager.strafe_left(sid)


@sio.event
async def strafe_right(sid):
    await room_manager.strafe_right(sid)


@sio.event
async def angle_left(sid):
    await room_manager.angle_left(sid)


@sio.event
async def angle_right(sid):
    await room_manager.angle_right(sid)


@sio.event
async def fire_gun(sid):
    await room_manager.fire_gun(sid)


@sio.event
async def power_up(sid):
    await room_manager.power_up(sid)


@sio.event
async def power_down(sid):
    await room_manager.power_down(sid)


@sio.event
async def next_bullet(sid):
    await room_manager.next_bullet(sid)


@sio.event
async def request_rooms(sid):
    await room_manager.send_room_list(sid)


@sio.event
async def create_room(sid, data):
    try:
        print(f'Creating room with name={data["name"]} for user {sid}')
        room_manager.create_room(data['name'])
        await room_manager.send_room_list()
    except RoomAlreadyExistsError:
        print(f'Room with name={data["name"]} already exists')
        await sio.emit('room_already_exists_error', data, room=sid)


async def send_objects_initial(*args, **kwargs):
    return await room_manager.send_objects_initial(*args, **kwargs)


async def send_updates(*args, **kwargs):
    return await room_manager.send_updates(*args, **kwargs)


async def tickPlayer(currentPlayer):
    if currentPlayer.lastHeartbeat < datetime.now().timestamp() - ConfigData.maxHeartbeatInterval:
        # sid = sockets[currentPlayer.id]  # old
        sid = currentPlayer.id
        await sio.emit('kick', f'Last heartbeat received over {ConfigData.maxHeartbeatInterval} ago.', room=sid)
        await sio.disconnect(sid)


async def moveloop():
    return await room_manager.move_loop()


async def gameloop():
    return await room_manager.game_loop()


# Web server logic
async def index(request):
    with open('../client/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')


async def favicon(request):
    return web.FileResponse('../client/favicon.ico')


def setInterval(func, timeout):
    async def wrapper(func, timeout):
        while True:
            await func()
            await sio.sleep(timeout / 1000)

    sio.start_background_task(wrapper, *(func, timeout))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    freeze_support()

    # object_manager, users, sockets = restart_object_manager()
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
    web.run_app(app, port=8000)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
