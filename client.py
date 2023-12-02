import json
import os
import socket
import sys
import threading


class FileClient:
    def __init__(self, log_callback=None):
        self.server_host = "localhost"
        self.server_port = 8888
        self.local_files = {}  # {file_name: file_path}
        self.lock = threading.Lock()  # To synchronize access to shared data
        self.hostname = None
        self.path = None
        self.stop_threads = False  # Flag to signal threads to terminate
        self.log_callback = log_callback
        self.client_socket = None
        self.server_connected = False

    def log(self, message):
        """Log a message to the console or using the Logs tab in the GUI.

        Args:
            message (str): The message to print
        """
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def login(self, hostname):
        """Connect to the server and set the client's hostname.

        Args:
            hostname (str): the client's hostname

        Returns:
            tuple[str, int]: the client's address (hostname, port)
        """
        with self.lock:
            if not self.client_socket:
                try:
                    self.client_socket = socket.socket(
                        socket.AF_INET, socket.SOCK_STREAM
                    )
                    self.client_socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                    )
                    self.client_socket.connect((self.server_host, self.server_port))
                    self.server_connected = True
                except Exception as e:
                    self.log(f"Error connect to server: {e}")
                    self.client_socket = None
                    return None

        client_address = self.init_hostname(self.client_socket, hostname)

        return client_address

    def start(self, client_address):
        """Start the client with receiving messages from server
        and listening for incoming connections from peers.

        Args:
            client_address (tuple[str, int]): the client's address (hostname, port)
        """
        self.receive_messages_thread = threading.Thread(
            target=self.receive_messages, daemon=True, args=(self.client_socket,)
        )
        self.receive_messages_thread.start()

        self.listener_thread = threading.Thread(
            target=self.start_listener, daemon=True, args=(client_address,)
        )
        self.listener_thread.start()

    def receive_messages(self, client_socket: socket.socket):
        """Receive messages from the server.

        Args:
            client_socket (socket.socket): the client' socket
        """
        with self.lock:
            while not self.stop_threads and self.server_connected:
                try:
                    recvd_data = client_socket.recv(1024).decode("utf-8", "replace")
                    if not recvd_data:
                        self.log("Connection closed by the server.")
                        break
                    data = json.loads(recvd_data)
                    print(f"currently at receive message {data}")

                    if data["header"] == "fetch" and data["payload"] is not None:
                        self.handle_fetch_sources(data)
                    else:
                        self.log(data["payload"]["message"])
                except ConnectionResetError:
                    self.log("Connection closed by the server.")
                    break
                except Exception as e:
                    if self.stop_threads:
                        break
                    self.log(f"Error receiving messages: {e}")
                    break
            self.server_connected = False

    def start_listener(self, client_address):
        """Start the listener socket to accept incoming connections.

        Args:
            client_address (tuple[str, int]): the client's address (hostname, port)
        """
        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind(client_address)
        self.listener_socket.listen()

        while not self.stop_threads:
            try:
                client_socket, addr = self.listener_socket.accept()
                threading.Thread(
                    target=self.handle_client, args=(client_socket, addr)
                ).start()
            except OSError as e:
                # Check if the error is due to stopping threads, ignore otherwise
                if not self.stop_threads:
                    self.log(f"Error accepting connection: {e}")
                    break

    def handle_client(self, client_socket: socket.socket, client_address):
        """Handle an incoming connection.

        Args:
            client_socket (socket.socket): the peer' socket
            client_address (tuple[str, int]): the peer's address (hostname, port)
        """
        while not self.stop_threads:
            raw_data = client_socket.recv(1024).decode("utf-8", "replace")
            if not raw_data:
                break
            data = json.loads(raw_data)

            if data["header"] == "ping":
                response = {
                    "header": "ping",
                    "type": 1,
                    "payload": {"success": True, "message": "pong"},
                }
                client_socket.sendall(json.dumps(response).encode("utf-8", "replace"))
                client_socket.close()
                break
            if data["header"] == "download":
                self.send_file(client_socket, data["payload"]["fname"])
                client_socket.close()
                break

    def send_file(self, client_socket: socket.socket, fname):
        """Send a file to a peer.

        Args:
            client_socket (socket.socket): the peer's socket
            fname (str): the file's name on the server

        Returns:
            bool: True if the file was sent successfully, False otherwise
        """
        local_name = [
            file for file in self.local_files if self.local_files[file] == fname
        ]
        if local_name:
            local_name = local_name[0]
        else:
            local_name = None
        if not os.path.exists(
            os.path.join(self.path, local_name)
        ) or not os.path.isfile(os.path.join(self.path, local_name)):
            reply = {
                "header": "download",
                "type": 1,
                "payload": {
                    "success": False,
                    "message": f"The file you requested {fname} is not available",
                    "length": None,
                },
            }
            client_socket.sendall(json.dumps(reply).encode("utf-8", "replace"))

        length = os.path.getsize(os.path.join(self.path, local_name))
        reply = {
            "header": "download",
            "type": 1,
            "payload": {
                "success": True,
                "message": f"{fname} is available",
                "length": length,
            },
        }
        binary_reply = json.dumps(reply).encode("utf-8", "replace")

        response_length = (len(binary_reply)).to_bytes(8, "big")
        client_socket.sendall(response_length + binary_reply)
        with open(os.path.join(self.path, local_name), "rb") as file:
            offset = 0
            try:
                while offset < length:
                    data = file.read(1024)
                    offset += len(data)
                    client_socket.sendall(data)
            except ConnectionResetError:
                self.log("Connection closed by peer.")
                return False
            except Exception as e:
                self.log(f"Error sending file: {e}")
                reply = {
                    "header": "download",
                    "type": 1,
                    "payload": {
                        "success": False,
                        "message": f"{e}",
                        "length": length,
                    },
                }
                client_socket.sendall(json.dumps(reply).encode("utf-8", "replace"))
                return False
        return True

    def init_hostname(self, client_socket: socket.socket, hostname: str):
        """Send the client's hostname to the server and receive the client's address.

        Args:
            client_socket (socket.socket): the client' socket
            hostname (_type_): the client's hostname

        Returns:
            tuple[str, int]: the client's address (hostname, port)
        """
        self.hostname = hostname
        self.send_hostname(client_socket)
        data = json.loads(client_socket.recv(1024).decode("utf-8", "replace"))
        if not data:
            return None

        if data["payload"]["success"] is False:
            self.log(data["payload"]["message"])
            return None
        address = data["payload"]["address"]
        address = (address[0], int(address[1]))
        return address

    def publish(self, client_socket: socket.socket, local_name: str, file_name: str):
        """Publish a file aliased as file_name to the server.

        Args:
            client_socket (socket.socket): the client' socket
            local_name (str): name of the file on the client's machine
            file_name (str): name of the file on the server

        Returns:
            bool: True if the file was published successfully, False otherwise
        """
        if self.server_connected is False:
            self.log("Not connected to server.")
            return False

        if len(local_name.split(".")) > 0:
            file_name = file_name + "." + local_name.split(".")[-1]

        if not os.path.exists(os.path.join(self.path, local_name)):
            self.log(f"File with local name '{local_name}' does not exist.")
            return False

        if local_name in self.local_files or file_name in self.local_files.values():
            self.log(
                f"File with local name '{local_name}'"
                f" or file name '{file_name}' already exists."
            )
            return False

        request = json.dumps(
            {
                "header": "publish",
                "type": 0,
                "payload": {"lname": local_name, "fname": file_name},
            }
        )

        try:
            client_socket.sendall(request.encode("utf-8", "replace"))
        except Exception as e:
            self.log(f"Error publish file to server: {e}")
            return False

        self.local_files[local_name] = file_name
        self.log(f"Published: '{local_name}' as '{file_name}'")
        return True

    def fetch(self, client_socket: socket.socket, file_name: str):
        """Fetch a file from the server into the client's directory.

        Args:
            client_socket (socket.socket): the client' socket
            file_name (str): the file's name on the server to fetch
        """
        if self.server_connected is False:
            self.log("Not connected to server.")
            return

        command = {"header": "fetch", "type": 0, "payload": {"fname": file_name}}
        request = json.dumps(command)
        try:
            client_socket.sendall(request.encode("utf-8", "replace"))
        except Exception as e:
            self.log(f"Error fetch file: {e}")

    def handle_fetch_sources(self, data):
        """Handle the fetch response from the server.

        Args:
            data (obj): response from the server
        """
        sources_data = data["payload"]
        fname = sources_data["fname"]
        if not sources_data["success"]:
            self.log("No other clients with the file found!")
            return
        address = sources_data["available_clients"][0]["address"]
        address = (address[0], int(address[1]))

        target_socket = self.p2p_connect(address)
        if target_socket:
            fetch_status = self.download_file(target_socket, fname)
            if fetch_status is True:
                self.log("Fetch successfully!")
            else:
                self.log("Fetch failed!")
                if os.path.isfile(os.path.join(self.path, fname)):
                    os.remove(os.path.join(self.path, fname))
            target_socket.close()
        else:
            self.log("Fetch failed!")

    def quit(self, client_socket: socket.socket):
        """Quit the client.

        Args:
            client_socket (socket): the client' socket
        """
        self.stop_threads = True
        client_socket.close()
        if hasattr(self, "listener_socket"):
            self.listener_socket.close()
        print("Client connection closed. Exiting.")
        sys.exit(0)

    def send_hostname(self, client_socket: socket.socket):
        """Send the client's hostname to the server.

        Args:
            client_socket (socket.socket): the client' socket
        """
        command = {
            "header": "sethost",
            "type": 0,
            "payload": {
                "hostname": self.hostname,
            },
        }
        request = json.dumps(command)
        client_socket.sendall(request.encode("utf-8", "replace"))

    def p2p_connect(self, target_address):
        """Connect to a peer.

        Args:
            target_address (tuple[str, int]): the peer's address (hostname, port)

        Returns:
            socket: the socket connected to the peer
        """
        try:
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # target_socket.connect((target_address, self.server_port))
            target_socket.connect(target_address)
            return target_socket
        except Exception as e:
            self.log(f"Error connecting to {target_address}: {e}")
            return None

    def download_file(self, target_socket: socket.socket, file_name):
        """Download a file from a peer.

        Args:
            target_socket (socket.socket): the peer's socket
            file_name (str): the file's name on the peer

        Returns:
            bool: True if the file was downloaded successfully, False otherwise
        """
        data = {
            "header": "download",
            "type": 0,
            "payload": {
                "fname": file_name,
            },
        }
        target_socket.sendall(json.dumps(data).encode("utf-8", "replace"))

        response_length = int.from_bytes(target_socket.recv(8), "big")
        recved_data = target_socket.recv(response_length).decode("utf-8", "replace")

        data = json.loads(recved_data)
        fname = file_name
        if os.path.isfile(os.path.join(self.path, fname)):
            fname = fname.split(".")[0] + "_copy." + fname.split(".")[1]
        length = data["payload"]["length"]
        if data["payload"]["success"] is False:
            self.log(data["payload"]["message"])
            return False

        self.log("Downloading file...")
        with open(os.path.join(self.path, fname), "wb") as file:
            try:
                offset = 0
                while offset < length:
                    recved = target_socket.recv(1024)

                    if not recved:
                        self.log("Connection closed by peer.")
                        return False

                    file.write(recved)
                    offset += 1024
                    self.log(f"Received {offset} bytes of data...")

                self.log("Download completed!")

            except ConnectionResetError:
                self.log("Connection closed by peer.")
                return False
            except Exception as e:
                self.log(f"Error receiving file: {e}")
                return False
        return True
