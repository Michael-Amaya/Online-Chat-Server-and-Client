import socket
import json
import common
import traceback
import threading
import tkinter as tk


#######################
#      Constants      #
#######################
MY_ID = -1
MY_SOCK = None
ONLINE_USERS = list()
CHAT_MESSAGES = list()
WINDOW_WIDTH=800
WINDOW_HEIGHT=600

# TKInter Vars
ID_VAR = None
CHAT_VAR = None
USERS_VAR = None
CHAT_MSG_VAR = None

#######################
#      Functions      #
#######################
def start_gui():
    '''Starts TKinter GUI'''
    global ID_VAR
    global CHAT_VAR
    global USERS_VAR
    global CHAT_MSG_VAR
    window = tk.Tk()
    # Build window
    ID_VAR = tk.StringVar()
    CHAT_VAR = tk.StringVar()
    USERS_VAR = tk.StringVar()
    CHAT_MSG_VAR = tk.StringVar()
    window.title('Chat Client by Michael Amaya')
    window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    window.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
    # Main Container (vbox)
    main_container = tk.Frame(window)
    main_container.pack(fill=tk.BOTH, expand=True)

    # Id:
    id_label = tk.Label(main_container, textvariable=ID_VAR)
    id_label.pack(fill=tk.X, padx=10, pady=5)

    # Hbox for chatbox and user list
    main_chat_hbox = tk.Frame(main_container)
    main_chat_hbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Main chatbox
    chat_box = tk.Text(main_chat_hbox, height=10, width=80)
    chat_box.config(state=tk.DISABLED)
    chat_box.delete(1.0, tk.END)
    chat_box.insert(tk.END, CHAT_VAR.get())
    chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # User list
    user_list = tk.Text(main_chat_hbox, height=10, width=20)
    user_list.config(state=tk.DISABLED)
    user_list.delete(1.0, tk.END)
    user_list.insert(tk.END, USERS_VAR.get())
    user_list.pack(side=tk.LEFT, fill=tk.BOTH)

    CHAT_VAR.trace_add('write', lambda *args: update_textbox(chat_box, CHAT_VAR))
    USERS_VAR.trace_add('write', lambda *args: update_textbox(user_list, USERS_VAR))

    def update_textbox(box: tk.Text, var:tk.StringVar):
        box.config(state=tk.NORMAL)
        box.delete(1.0, tk.END)
        box.insert(tk.END, var.get())
        box.config(state=tk.DISABLED)
        box.see(tk.END)

    # User Controls
    user_controls_hbox = tk.Frame(main_container)
    user_controls_hbox.pack(fill=tk.X, padx=10, pady=5)

    # Chat message to send
    message_to_send = tk.Entry(user_controls_hbox, textvariable=CHAT_MSG_VAR)
    message_to_send.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Define function when submit happens
    def on_submit(sock):
        text = CHAT_MSG_VAR.get()
        if not text:
            return
        print(f"User is sending: {text}")

        chat_event = common.ChatEvent(MY_ID, text)
        common.send_to_socket(sock, chat_event)
        CHAT_MSG_VAR.set('')

    # Submit button
    send_button = tk.Button(user_controls_hbox, text="Send", command=lambda: on_submit(MY_SOCK))
    send_button.pack(side=tk.LEFT, padx=5)
    message_to_send.bind('<Return>', lambda event: send_button.invoke())

    # Blocking main loop
    window.mainloop()


def render_ui():
    '''Re-renders TKinter UI'''
    online_user_str = ''
    chat_messages_str = ''
    for user in ONLINE_USERS:
        online_user_str += f'{user.user_id}: ONLINE\n'

    for msg in CHAT_MESSAGES:
        chat_messages_str += f'{msg.user_id}: {msg.chat_msg}\n'

    id_val = f'Welcome. Your ID is {MY_ID}'
    if ID_VAR and MY_ID != -1 and ID_VAR != id_val:
        ID_VAR.set(id_val)

    if CHAT_VAR and CHAT_VAR.get() != chat_messages_str:
        CHAT_VAR.set(chat_messages_str)
    if USERS_VAR and USERS_VAR.get() != online_user_str:
        USERS_VAR.set(online_user_str)


#######################
#       Threads       #
#######################
class EventProcessorThread(threading.Thread):
    '''Class to take action on received messages'''
    def __init__(self, c_sock, extra_events, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.c_sock = c_sock
        self.extra_events = extra_events

    def run(self):
        try:
            # Process other events first, then get more events
            for event in self.extra_events:
                if not event:
                    continue
                self.process_event(event)

            # Run main loop to get more events
            while True:
                event = self.c_sock.recv(common.MAX_MESSAGE_BUFFER).decode('utf-8')
                if not event:
                    continue
                split_event = event.split('\n')
                for ea_event in split_event:
                    self.process_event(ea_event)
        except Exception:
            pass
        finally:
            self.c_sock.close()

    def process_event(self, event):
        '''Processes all events, event is a dict'''
        if not event:
            # Blank event, multiple events have a trailing empty event
            return
        event_parsed = json.loads(event)
        if common.PingEvent.is_ping_event(event_parsed):
            ping_event = common.PingEvent.from_dict(event_parsed)
            if ping_event.ping_type != common.PingType.PING.value:
                raise ValueError(f'Invalid Event: PingEvent: {event_parsed}')
            ping_event.ping_type = common.PingType.PONG
            common.send_to_socket(self.c_sock, ping_event)

        elif common.HelloEvent.is_hello_event(event_parsed):
            raise ValueError("Invalid Event: duplicate HelloEvent")

        elif common.UserJoinedEvent.is_user_joined_event(event_parsed):
            user_joined_event = common.UserJoinedEvent.from_dict(event_parsed)
            print(f'A user is connected with ID {user_joined_event.user_id}')
            ONLINE_USERS.append(common.Client(user_joined_event.user_id))

        elif common.UserLeftEvent.is_user_left_event(event_parsed):
            user_left_event = common.UserLeftEvent.from_dict(event_parsed)
            print(f'A user with ID {user_left_event.user_id} has left')
            for i, user in enumerate(ONLINE_USERS.copy()):
                if user_left_event.user_id == user.user_id:
                    ONLINE_USERS.pop(i)
                    break

        elif common.ChatEvent.is_chat_event(event_parsed):
            chat_event = common.ChatEvent.from_dict(event_parsed)
            CHAT_MESSAGES.append(chat_event)

        else:
            print(event_parsed)
            raise ValueError("Invalid Event: Event")
        render_ui()


#######################
#         Main        #
#######################
if __name__ == '__main__':
    print("Client starting..")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((common.HOST, common.PORT))
        print("Connected!")

        # Create hello message to get an ID
        print("Saying Hello")
        hello_event = common.HelloEvent()
        common.send_to_socket(client_socket, hello_event)
        hello_response = client_socket.recv(common.MAX_MESSAGE_BUFFER).decode('utf-8')
        # Remove extra events to be parsed later
        events = hello_response.split('\n')
        extra_events = events[1:]
        # Set hello event
        hello_response = events[0]
        hello_response_parsed = json.loads(hello_response)
        if not common.HelloEvent.is_hello_event(hello_response_parsed):
            raise ValueError("Invalid Event: HelloEvent")
        hello_event = common.HelloEvent.from_dict(hello_response_parsed)

        client = common.Client(hello_event.user_id)
        print(f"Got response! My ID is {client.user_id}")
        MY_ID = client.user_id
        MY_SOCK = client_socket
        # Start event processor thread
        event_processor = EventProcessorThread(client_socket, extra_events, daemon=True)
        event_processor.start()

        # Start GUI
        start_gui()
    except:
        print(traceback.format_exc())
    finally:
        print("Closing connection")
        client_socket.close()
