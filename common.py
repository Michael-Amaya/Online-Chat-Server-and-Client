import enum
import json


# Local Constants
HOST = 'localhost'
PORT = 5050
MAX_MESSAGE_BUFFER=4096
SERVER_TICK_RATE = 30
SERVER_FPS = 1 / SERVER_TICK_RATE # 1 because it's 1 tick per tick rate


class PingType(enum.Enum):
    '''Enum to differentiate ping types'''
    PING = 'PING'
    PONG = 'PONG'


class EventType(enum.Enum):
    '''Enum to differentiate events'''
    HELLO = 'HELLO'
    USER_JOINED = 'USER_JOINED'
    USER_LEFT = 'USER_LEFT'
    PING = 'PING'
    CHAT = 'CHAT'


class Event:
    '''Interface for basic events'''
    def __init__(self, type: EventType, *args, **kwargs):
        if not isinstance(type, EventType):
            raise ValueError(f"Invalid event type: {type}!")
        self.what = 'Event'
        self.type = type

    def to_dict(self):
        '''Convert event to a dictionary'''
        to_return = {}
        for key, val in self.__dict__.items():
            if isinstance(val, enum.Enum):
                to_return[key] = val.value
            else:
                to_return[key] = val
        return to_return

    @classmethod
    def from_dict(cls, data):
        '''Convert a dictionary to an event'''
        # Verify it's an event
        if not cls.validate_event(data):
            raise ValueError(f'Could not verify event when parsing: {data}')
        del data['type']
        return cls(**data)

    @classmethod
    def validate_event(cls, data: dict):
        '''Validates that some dict is an event'''
        return 'what' in data and data['what'] == 'Event'


class HelloEvent(Event):
    '''Event for server saying hello to client'''
    def __init__(self, *args, user_id = None,  **kwargs):
        super().__init__(EventType.HELLO, *args, **kwargs)
        self.user_id = user_id

    @classmethod
    def is_hello_event(cls, data):
        '''Checks if some dictionary is a hello event'''
        return cls.validate_event(data) and data['type'] == EventType.HELLO.value


class UserJoinedEvent(Event):
    '''Event for server saying hello to client'''
    def __init__(self, user_id, *args, **kwargs):
        super().__init__(EventType.USER_JOINED, *args, **kwargs)
        self.user_id = user_id

    @classmethod
    def is_user_joined_event(cls, data):
        '''Checks if some dictionary is a hello event'''
        return cls.validate_event(data) and data['type'] == EventType.USER_JOINED.value


class UserLeftEvent(Event):
    '''Event for server saying hello to client'''
    def __init__(self, user_id, *args, **kwargs):
        super().__init__(EventType.USER_LEFT, *args, **kwargs)
        self.user_id = user_id

    @classmethod
    def is_user_left_event(cls, data):
        '''Checks if some dictionary is a hello event'''
        return cls.validate_event(data) and data['type'] == EventType.USER_LEFT.value


class PingEvent(Event):
    '''Event for server saying hello to client'''
    def __init__(self, ping_type:PingType, *args, **kwargs):
        super().__init__(EventType.PING, *args, **kwargs)
        self.ping_type = ping_type

    @classmethod
    def is_ping_event(cls, data):
        '''Checks if some dictionary is a hello event'''
        return cls.validate_event(data) and data['type'] == EventType.PING.value


class ChatEvent(Event):
    '''Event for server saying hello to client'''
    def __init__(self, user_id, chat_msg, *args, **kwargs):
        super().__init__(EventType.CHAT, *args, **kwargs)
        self.user_id = user_id
        self.chat_msg = chat_msg

    @classmethod
    def is_chat_event(cls, data):
        '''Checks if some dictionary is a hello event'''
        return cls.validate_event(data) and data['type'] == EventType.CHAT.value


class Client:
    '''Class to handle client properties'''
    def __init__(self, user_id):
        self.user_id = user_id


def send_to_socket(destination_socket, data: Event, user_id=None):
    '''Takes an event, breaks down to a dict, and sends to socket with new line'''
    if not isinstance(data, dict):
        data = data.to_dict()
    to_send = (json.dumps(data) + '\n').encode('utf-8')
    if not destination_socket:
        return
    try:
        destination_socket.sendall(to_send)
    except OSError:
        print(f"Socket error on id {user_id}. A client disconnected possibly?")
