import asyncio
from asyncio import Future
from dataclasses import dataclass, field
from datetime import datetime
from random import random, choice
from typing import Dict, Optional

from urllib.parse import parse_qs

from socketio import AsyncServer

from .ObjectManager import ObjectManager
from .Config import ConfigData
from .util import validNick
from .vector import Vector
from .PlayerInfo import PlayerInfo

# Type Aliases
Sid = str
RoomName = str


class RoomAlreadyExistsError(ValueError):
    """Room already exists error."""
    pass


class RoomDoesNotExistError(KeyError):
    """Room does not exist error."""
    pass


@dataclass
class Room:
    """
    A Room is an interface between the server and an ObjectManager to handle socket related events.
    Physics-related and game-play functionality lies within the ObjectManager, but Rooms handle connection
    and disconnection as well as messaging.
    """
    name: RoomName
    sio: AsyncServer
    object_manager: Optional[ObjectManager] = None
    connected_sids: Dict[Sid, bool] = field(default_factory=dict)  # Key is sid, value is if they are still connected

    async def connect_player(self, sid: Sid, player: Dict):
        self.connected_sids[sid] = True
        if self.object_manager:
            object_manager, users, sockets = self.object_manager, self.object_manager.users, self.object_manager.sockets
            player = PlayerInfo.from_dict(player, object_manager.tanks)
            print(f'[INFO] Player {player.name}connecting to room {self.name}!')

            if player.id in users:
                print('[INFO] Player ID is already connected, kicking.')
                await self.sio.disconnect(sid)
            elif not validNick(player.name):
                await self.sio.emit('kick', 'Invalid username.')
                await self.sio.disconnect(sid)
            else:
                async with self.sio.session(sid) as session:
                    print(f'[INFO] Player {player.name} connected to room {self.name}!')
                    sockets[player.id] = sid
                    session['currentPlayer'] = player
                    session['currentPlayer'].lastHeartbeat = datetime.now().timestamp()
                    object_manager.create_tank(longitude=random() * 360,
                                               home_planet=choice(list(object_manager.planets.values())),
                                               sid=sid,
                                               color=str(int(random() * 360)),
                                               is_player=True)

                    users.append(session['currentPlayer'])

                    await self.sio.emit('playerJoin', {'name': session['currentPlayer'].name}, room=self.name)

                    await self.sio.emit('gameSetup',
                                        {'gameWidth': 1024,  # c.gameWidth,
                                         'gameHeight': 1024,  # c.gameHeight
                                         },
                                        room=sid)

    def disconect_player(self, sid: Sid):
        self.connected_sids[sid] = False
        if self.object_manager:
            self.object_manager.remove_player(sid)

    async def send_objects_initial(self, *args, **kwargs):
        if self.object_manager:
            return await self.object_manager.send_objects_initial(self.sio, *args, **kwargs)

    async def send_updates(self, *args, **kwargs):
        if self.object_manager:
            return await self.object_manager.send_updates(self.sio, *args, **kwargs)


class RoomManager:
    def __init__(self, socket_io_server: AsyncServer):
        self.rooms: Dict[RoomName, Room] = {'default': Room('default', socket_io_server)}
        self.connected_players: Dict[Sid, RoomName] = {}
        self.sio = socket_io_server

    def create_room(self, name: RoomName, level_path: str = '') -> None:
        """
        Create a room to which players can later be added. Also initializes the room's Object Manager
        :param level_path: file path to the level file
        :param name: RoomName representing the name of the room to be created
        :raise RoomAlreadyExistsError: if the room already exists
        :return: None
        """
        if name not in self.rooms:
            self.rooms[name] = Room(name, self.sio, ObjectManager(file_path=level_path))
        else:
            raise RoomAlreadyExistsError(f'Room with name {name} already exists.')

    def restart_room(self, name: RoomName, level_path: str = '') -> None:
        """
        Restart an already existent room.
        :param name: RoomName representing the name of the room to be restarted
        :param level_path: file path to the level file
        :return None
        """
        try:
            self.rooms[name].object_manager = ObjectManager(file_path=level_path)
        except KeyError:
            raise RoomDoesNotExistError(f'Room with name {name} does not exist')

    def delete_room(self, name: RoomName) -> None:
        """
        Delete a previous created room.
        :param name: RoomName representing the name of the room to be created
        :raise RoomDoesNotExistError: if there is no room with the given name
        :return None
        """
        try:
            # TODO: Disconnect all the tanks upon room deletion. Create a function in Object manager to do so?
            del self.rooms[name]
        except KeyError:
            raise RoomDoesNotExistError(f'Room with name {name} does not exist')

    async def connect_player(self, sid: Sid, socket, auth) -> None:
        """
        Create a new player in the default room.
        :param socket:
        :param auth:
        :param sid: socket-id of the player to connect
        """

        # Handle Socket connection and persistence
        socket_parse = parse_qs(socket['QUERY_STRING'])
        session_type = socket_parse['type'][0]
        print('A user connected!', session_type)
        async with self.sio.session(sid) as session:
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

        # Add the player to the default room.
        await self.rooms['default'].connect_player(sid, player={})
        self.connected_players[sid] = 'default'
        self.sio.enter_room(sid, 'default')

    def disconnect_player(self, sid: Sid) -> None:
        """
        Disconnects the player from their room.
        :param sid: socket-id of the player to disconnect
        """
        self.get_room_from_sid(sid).disconect_player(sid)
        self.sio.leave_room(sid, self.connected_players[sid])  # Leave the sio room
        # Go ahead and remove them from the connected players list to reduce memory usage
        # del self.connected_players[sid]
        self.connected_players[sid] = ''

    async def move_player(self, sid: Sid, new_room: RoomName, player_info_dict: Dict) -> None:
        """
        Move a player between rooms.
        :param player_info_dict:
        :param new_room: RoomName representing the name of the room the player will be moved to
        :param sid: socket-id of the player to move
        :return:
        """
        # Disconnect player from current room
        self.get_room_from_sid(sid).disconect_player(sid)

        # Move the socket room for messaging
        self.sio.leave_room(sid, self.connected_players[sid])  # Leave the sio room
        if new_room not in self.rooms:
            raise RoomDoesNotExistError(f'Cannot move player to room {new_room} which does not exist.')
        self.sio.enter_room(sid, new_room)

        # Connect player to new room
        self.connected_players[sid] = new_room
        await self.rooms[new_room].connect_player(sid=sid, player=player_info_dict)


    async def send_chat(self, sender_sid: Sid, msg: Dict):
        """
        Send a chat message to all of the players in the same room as sender_sid.
        :param sender_sid: the socket-id of the player sending the message
        :param msg: the message being sent
        :return: None
        """
        _sender = msg['sender'].replace('/(<([^>]+)>)/ig', '')
        _message = msg['message'].replace('/(<([^>]+)>)/ig', '')
        now: datetime = datetime.now()
        if ConfigData.logChat == 1:
            print(f'[CHAT] [{now.hour:02d}:{now.minute:02d}] {_sender}: {_message}')
        return await self.sio.emit('serverSendPlayerChat', {'sender': _sender, 'message': _message[:35]},
                                   skip_sid=sender_sid, room=self.connected_players[sender_sid])

    def get_room_from_sid(self, sid: Sid):
        """
        Helper function that gets the room of a given sid.
        :param sid: socket-id of the user
        :return:
        """
        return self.rooms[self.connected_players[sid]]

    def get_object_manager_from_sid(self, sid: Sid):
        """
        Helper function that gets the object manager of a given sid.
        :param sid: socket-id of the user
        :return: ObjectManager belonging to the room in which the sid is connected.
        """
        return self.get_room_from_sid(sid).object_manager

    async def strafe_left(self, sid: Sid) -> None:
        """
        Sends a strafe left command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).strafe_left(sid)

    async def strafe_right(self, sid: Sid) -> None:
        """
        Sends a strafe right command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).strafe_right(sid)

    async def angle_left(self, sid: Sid) -> None:
        """
        Sends an angle left command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).angle_left(sid)

    async def angle_right(self, sid: Sid) -> None:
        """
        Sends an angle right command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).angle_right(sid)

    async def fire_gun(self, sid: Sid) -> None:
        """
        Sends a fire gun command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).fire_gun_sid(sid)

    async def power_up(self, sid: Sid) -> None:
        """
        Sends a power up command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).power_up(sid)

    async def power_down(self, sid: Sid) -> None:
        """
        Sends a power down command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).power_down(sid)

    async def next_bullet(self, sid: Sid) -> None:
        """
        Sends a next bullet command to the ObjectManager containing the sid.
        :param sid: socket-id of the user
        :return: None
        """
        self.get_object_manager_from_sid(sid).next_bullet(sid)

    async def send_objects_initial(self, *args, **kwargs):
        return await asyncio.gather(*[room.send_objects_initial(*args, **kwargs) for room in self.rooms.values()])

    async def send_updates(self, *args, **kwargs):
        return await asyncio.gather(*[room.send_updates(*args, **kwargs) for room in self.rooms.values()])

    async def move_loop(self) -> Future:
        """
        Performs the movement step in each room.
        :return: A Future containing each coroutine of each move step in each room
        """
        return asyncio.gather(*[room.object_manager.move(self.sio) for room in self.rooms.values() if room.object_manager])

    async def respawn(self, sid) -> None:
        await self.send_objects_initial(room=sid)
        async with self.sio.session(sid) as session:
            if session['currentPlayer'].id in self.connected_players:
                # users.remove(session['currentPlayer'].id)
                pass
            await self.sio.emit('welcome', session['currentPlayer'].to_json(), room=sid)
            print('[INFO] User ' + session['currentPlayer'].name + ' respawned!')
