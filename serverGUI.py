# import platform
import threading
import PySimpleGUI as sg

from server import ServerLogic

class ServerGUI:
    def __init__(self, host, port):
        self.server = ServerLogic(
            host,
            port,
            log_callback=self.log_message,
            log_request_callback=self.log_request,
        )

        # Layout
        layout = [
            [sg.Text('Logs', font=('Helvetica', 24, 'bold'))],
            [sg.Multiline("", size=(60, 10), key='-LOG-', autoscroll=True,  reroute_cprint=True, font=('Helvetica', 12))],
            [sg.Text('Requests', font=('Helvetica', 24, 'bold'))],
            [sg.Multiline(size=(60, 10), key='-REQUEST_LOG-', disabled=True, autoscroll=True, font=('Helvetica', 12))],
            [sg.InputText(key='-COMMAND-', size=(40, 1), font=('Helvetica', 12)), sg.Button('Send Command', key='-SEND_COMMAND-', font=('Helvetica', 10))],
            [sg.Button('Start Server', key='-START_SERVER-', font=('Helvetica', 10)),
             sg.Button('Stop Server', key='-STOP_SERVER-', font=('Helvetica', 10))]
        ]

        self.window = sg.Window('P2P Server GUI', layout, finalize=True)
        
    def start_server(self):
        self.log_message("Starting server...")
        self.server.start()

    def stop_server(self):
        self.log_message("Server stopped.\n")
        self.server.shutdown()

    def send_command(self, command):
        threading.Thread(target=self.server.process_server_command, args=(command,)).start()

    def on_close(self):
        self.server.shutdown()
        self.window.close()

    def log_message(self, message):
        self.window["-LOG-"].print(message, end="\n")

    def log_request(self, message):
        self.window["-REQUEST_LOG-"].print(message, end="\n")

if __name__ == '__main__':
    gui = ServerGUI("localhost", 50000)

    while True:
        event, values = gui.window.read()

        if event == sg.WINDOW_CLOSED:
            gui.on_close()
            break
        elif event == '-START_SERVER-':
            gui.start_server()
        elif event == '-STOP_SERVER-':
            gui.stop_server()
        elif event == '-SEND_COMMAND-':
            gui.send_command()

