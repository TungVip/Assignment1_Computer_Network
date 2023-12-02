import os
import PySimpleGUI as sg
import threading

from client import FileClient

class FileClientGUI:
    def __init__(self):
        self.client = FileClient(log_callback=self.log)
        self.path = None
        self.files = None

        self.layout = [
            [sg.Button("Connect", key="connect")],
            [sg.Text("Hostname:"), sg.InputText(key="hostname"), sg.Button("Submit", key="submit_hostname")],
            [sg.Text("Choose Path:"), sg.InputText(key="path"), sg.FolderBrowse(key="browse_path")],
            [sg.Multiline(size=(60, 20), key="logs", disabled=True)],
            [sg.Multiline(size=(60, 20), key="repo", disabled=True)],
            [sg.Text("Publish:"), sg.InputText(key="file_path", readonly=True), sg.FileBrowse(key="browse_file"),
             sg.InputText(key="file_name"), sg.Button("Publish", key="publish")],
            [sg.Text("Fetch:"), sg.InputText(key="fetch_file"), sg.Button("Fetch", key="fetch")],
            [sg.Button("Quit", key="quit")]
        ]

        self.window = sg.Window("P2P Client GUI", self.layout)

        while True:
            event, values = self.window.read()

            if event == sg.WINDOW_CLOSED or event == "quit":
                self.quit_client()
                break
            elif event == "connect":
                self.connect_to_server()
            elif event == "submit_hostname":
                self.init_hostname(values["hostname"])
            elif event == "browse_path":
                self.init_path()
            elif event == "browse_file":
                self.browse_file()
            elif event == "publish":
                self.publish(values["file_path"], values["file_name"])
            elif event == "fetch":
                self.fetch(values["fetch_file"])

    def init_path(self):
        path = sg.popup_get_folder("Choose Path")
        if path and os.path.exists(path):
            self.client.path = path
            self.window["path"].update(path)
            self.files = {file: False for file in os.listdir(self.client.path) if os.path.isfile(os.path.join(self.client.path, file))}
            self.window["hostname"].update(disabled=False)

    def init_hostname(self, hostname):
        if hostname:
            try:
                client_address = self.client.login(hostname)
                self.log(f"Client address: {client_address}")
                if client_address:
                    self.log(f"Hostname '{hostname}' set successfully.")
                    threading.Thread(target=self.client.start, args=(client_address,)).start()
                    self.window["hostname"].update(disabled=True)
                    self.window["repo"].update(f"Current directory: {self.client.path}\n")
                    self.window["submit_hostname"].update(disabled=True)
                    self.window["browse_path"].update(disabled=True)
                    self.window["file_path"].update(readonly=False)
                    self.window["file_name"].update(disabled=False)
                    self.window["publish"].update(disabled=False)
                    self.window["fetch_file"].update(disabled=False)
                    self.process_file(first_time=True)
            except Exception as e:
                self.log(f"Error setting hostname: {e}")
        else:
            self.log("Hostname cannot be empty.")

    def browse_file(self):
        file_path = sg.popup_get_file("Choose File", initial_folder=self.client.path)
        if file_path and os.path.exists(file_path):
            if os.path.dirname(file_path) == self.client.path:
                self.window["file_path"].update(readonly=False)
                self.window["file_path"].update(file_path)
                self.window["file_path"].update(readonly=True)
            else:
                self.log(f"Choose file in the {self.client.path} directory!")

    def publish(self, file_path, file_name):
        local_name = file_path.split("/")[-1]
        if not file_name or not local_name:
            self.log("Error publishing file: Please fill in the blank!")
            return
        try:
            publish_status = self.client.publish(self.client.client_socket, local_name, file_name)
            if publish_status:
                self.window["file_path"].update(readonly=False)
                self.window["file_path"].update("")
                self.window["file_path"].update(readonly=True)
                self.window["file_name"].update("")
        except Exception as e:
            self.log(f"Error publishing file: {e}")

    def fetch(self, file_name):
        if not file_name:
            self.log("Error fetching file: File name cannot be blank!")
            return
        try:
            self.client.fetch(self.client.client_socket, file_name)
            self.window["fetch_file"].update("")
        except Exception as e:
            self.log(f"Error fetching file: {e}")

    def quit_client(self):
        self.client.quit(self.client.client_socket)
        self.window.close()

    def log(self, message):
        self.window["logs"].update(disabled=False)
        self.window["logs"].print(message, end="\n")
        self.window["logs"].update(disabled=True)

    def process_file(self, first_time=False):
        if self.client.path is not None:
            new_files = [file for file in list(self.client.local_files.keys()) if self.files[file] is False]
            dir_unchange = list(self.files.keys()) == [file for file in os.listdir(self.client.path) if os.path.isfile(os.path.join(self.client.path, file))]
            publish_unchange = len(list(self.client.local_files.keys())) == 0 or len(new_files) == 0

            if first_time is True or dir_unchange is False or publish_unchange is False:
                self.window["repo"].update(disabled=False)
                self.window["repo"].update("Current directory: {self.client.path}\n")
                self.files = {file: False for file in os.listdir(self.client.path) if os.path.isfile(os.path.join(self.client.path, file))}

                all_files = list(self.files.keys())
                all_files.sort()
                for file in all_files:
                    if file in self.client.local_files and self.client.local_files[file] is not None:
                        self.window["repo"].update(f"\n{file[:25] + '...' if len(file) > 25 else file} - {self.client.local_files[file]}", append=True)
                        self.files[file] = True
                    else:
                        self.window["repo"].update(f"\n{file[:35] + '...' if len(file) > 35 else file} (not published)", append=True)
                self.window["repo"].update(disabled=True)

        sg.popup_timed("Processing Files...", auto_close_duration=5000, non_blocking=True)

if __name__ == "__main__":
    gui = FileClientGUI()
