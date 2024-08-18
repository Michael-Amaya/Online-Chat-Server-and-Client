import socket
import threading
import json
import common
import time
import traceback


#######################
#      Constants      #
#######################
CHAT_HISTORY_TO_SEND = 10


#######################
#       Structs       #
#######################
# Python has no structs so I have to make it a class: boo!
# Lock order: ActiveConnections -> EventQueue -> ChatMessages


class ActiveConnections:
    '''Struct for active connection and lock'''
    lock = threading.Lock()
    registry = dict()


class EventQueue:
    '''Struct for events queue and lock'''
    items = list()
    lock = threading.Lock()


class ChatMessages:
    '''Struct for chat messages and lock'''
    items = list()
    lock = threading.Lock()


#######################
#       Threads       #
#######################
class TickThread(threading.Thread):
    '''Class to handle events at every tick'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        while True:
            with ActiveConnections.lock and EventQueue.lock:
                for connection_thread, _ in ActiveConnections.registry.items():
                    for event in EventQueue.items:
                        if not connection_thread.c_socket:
                            continue
                        common.send_to_socket(connection_thread.c_socket, event)
                EventQueue.items.clear()
            time.sleep(common.SERVER_FPS)


class ClientThread(threading.Thread):
    '''Class to handle clients connected to server'''
    def __init__(self, c_socket, properties, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.c_socket = c_socket
        self.properties = properties

    def run(self):
        print(f"Client with ID {self.properties.user_id} Connected!")
        try:
            while True:
                events = self.c_socket.recv(common.MAX_MESSAGE_BUFFER)
                if not events:
                    continue
                events = events.decode('utf-8')
                event_arr = events.split('\n')
                for event in event_arr:
                    if not event:
                        continue
                    self.process_event(event)
                time.sleep(common.SERVER_FPS)
        except Exception as e:
            print(f"There was an error when processing event for client id {self.properties.user_id}: {e}")
        finally:
            print(f"Client with ID {self.properties.user_id} closed connection")
            # Remove from active connection
            with ActiveConnections.lock:
                for c_sock, c_props in ActiveConnections.registry.copy().items():
                    if self.properties.user_id == c_props.user_id:
                        del ActiveConnections.registry[c_sock]
                        break
            # Send disconnected event
            EventQueue.items.append(common.UserLeftEvent(self.properties.user_id))
            self.c_socket.close()

    def process_event(self, event):
        '''Processes events on the server'''
        event_parsed = json.loads(event)
        event_to_propagate  = None

        # Check if message is an event
        if not common.Event.validate_event(event_parsed):
            raise ValueError(
                f"Invalid Event: message: {event_parsed} on id {self.properties.user_id}"
            )

        # Check event types
        if common.HelloEvent.is_hello_event(event_parsed):
            hello_event = common.HelloEvent.from_dict(event_parsed)
            if hello_event.user_id is not None:
                raise ValueError(
                    f"Invalid Event: HelloEvent: {event_parsed} on id {self.properties.user_id}"
                )
            hello_event.user_id = self.properties.user_id
            # to_send = json.dumps(hello_event.to_dict())
            if not self.c_socket:
                return

            common.send_to_socket(self.c_socket, hello_event)
            # self.c_socket.sendall(to_send.encode('utf-8'))

            # Send other connections
            with ActiveConnections.lock:
                for _, conn_props in ActiveConnections.registry.items():
                    to_send = common.UserJoinedEvent(conn_props.user_id)
                    if not self.c_socket:
                        continue
                    if conn_props.user_id != self.properties.user_id:
                        common.send_to_socket(self.c_socket, to_send)

            # Send last 10 chats
            with ChatMessages.lock:
                for chat in ChatMessages.items[-CHAT_HISTORY_TO_SEND:]:
                    common.send_to_socket(self.c_socket, chat)

            # also send a ping so we can setup ping-pong
            ping_event = common.PingEvent(common.PingType.PING)
            common.send_to_socket(self.c_socket, ping_event)

            event_to_propagate  = common.UserJoinedEvent(self.properties.user_id)

        elif common.PingEvent.is_ping_event(event_parsed):
            # We need to handle the ping event
            ping_event = common.PingEvent.from_dict(event_parsed)
            if ping_event.ping_type != common.PingType.PONG.value:
                raise ValueError(
                    f"Invalid Event: PingEvent: {event_parsed} on id {self.properties.user_id}"
                )
            ping_event.ping_type = common.PingType.PING
            common.send_to_socket(self.c_socket, ping_event)
            # No event to propagate so we don't set it

        elif common.ChatEvent.is_chat_event(event_parsed):
            chat_event = common.ChatEvent.from_dict(event_parsed)
            with ChatMessages.lock:
                ChatMessages.items.append(chat_event)
            print(f'A chat message was sent: {chat_event.chat_msg} from user {chat_event.user_id}')
            event_to_propagate  = chat_event

        else:
            raise ValueError(
                f"Invalid Event: Event: {event_parsed} on id {self.properties.user_id}"
            )

        # Propagate the event to others
        if event_to_propagate :
            # Add to event queue so other events can work it
            with EventQueue.lock:
                EventQueue.items.append(event_to_propagate )


#######################
#         Main        #
#######################
if __name__ == '__main__':
    print("Server Starting...")
    id_counter = 0


    # Start event queue thread
    tick = TickThread()
    tick.start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((common.HOST, common.PORT))
        server_socket.listen()
        print(f"Listening at {common.HOST}, port {common.PORT}")
        while True:
            client, _ = server_socket.accept()
            client_properties = common.Client(id_counter)
            client_thread = ClientThread(client, client_properties)
            client_thread.start()
            with ActiveConnections.lock:
                ActiveConnections.registry[client_thread] = client_properties
            id_counter += 1
    except:
        traceback.format_exc()
    finally:
        server_socket.close()
