import json
import select
import socket
import sys
import threading
from typing import Any


class ServerLogic:
    def __init__(self, host, port, log_callback=None, log_request_callback=None):       # Done
        self.host = host
        self.port = port
        # clients -> {client_address: {"hostname": hostname, "files": [dictionary of files]}}
        self.clients = (
            {}
        )  
        self.lock = threading.Lock()
        self.is_running = False
        self.log_callback = log_callback
        self.log_request_callback = log_request_callback

    def log(self, message):     # Done
        """Log a message to the console or to a callback function

        Args:
            message (str): The message to log
        """
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def log_request(self, message):     # Done
        """Log a request to the console or to a callback function

        Args:
            message (str): The message to log
        """
        if self.log_request_callback:
            self.log_request_callback(message)
        else:
            print(message)

    def start(self):        # Done
        """Start the server in a separate thread"""
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()

    def run_server(self):       # Done
        """Setup socket for the server and start listening for connections"""
        with self.lock:
            if self.is_running:
                self.log("Server is already running!")
                return
            else:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, self.port))
                server_socket.listen(5)

                self.is_running = True
                self.log(f"Server listening on {self.host}:{self.port}")

        while self.is_running:
            try:
                client_socket, client_address = server_socket.accept()
                threading.Thread(
                    target=self.handle_client,
                    daemon=True,
                    args=(client_socket, client_address),
                ).start()
            except OSError as e:
                # Check if the error is due to stopping the server, ignore otherwise
                if not self.is_running:
                    break
                else:
                    self.log(f"Error accepting connection: {e}")

    def handle_client(self, client_socket, client_address):
        """Handle a client connection

        Args:
            client_socket (socket): The client' socket
            client_address (tuple[str, int]): The client's address
        """
        with self.lock:
            self.clients[client_address] = {
                "client_socket": client_socket,
                "hostname": None,
                "status": "online",
                "files": [],
            }

        if self.is_running:
            self.log(f"New connection from {client_address}")

        while self.clients[client_address]["status"] == "online" and self.is_running:
            try:
                data = client_socket.recv(1024).decode("utf-8", "replace")
                if not data:
                    break

                try:
                    data = json.loads(data)
                except Exception as e:
                    self.log(f"Error receiving command: {e}")

                self.process_command(client_socket, client_address, data)

            except ConnectionResetError:
                self.log("Connection closed by the client.")
                break
            
            except Exception as e:
                if self.clients[client_address]["status"] == "offline":
                    break
                self.log(f"Error handling client {client_address}: {e}")
                break

        with self.lock:
            if client_address in self.clients:
                del self.clients[client_address]
            if client_socket:
                client_socket.close()
            if self.is_running:
                self.log(f"Connection from {client_address} closed")

    def process_command(self, client_socket, client_address, command):
        """Process a command received from a client

        Args:
            client_socket (socket): The client' socket
            client_address (tuple[str, int]): The client's address
            command (str): The command to process
        """
        with self.lock:
            if command["header"] == "publish":
                self.log_request(
                    f">>> Client {client_address}: {command['header'].upper()}\n---\n"
                )
                self.publish(
                    client_address,
                    command["payload"]["fname"],
                )
            elif command["header"] == "fetch":
                self.log_request(
                    f">>> Client {client_address}: {command['header'].upper()}\n---\n"
                )
                self.fetch(client_socket, client_address, command["payload"]["fname"])
            elif command["header"] == "sethost":
                self.log_request(
                    f">>> Client {client_address}: {command['header'].upper()}\n---\n"
                )
                self.set_hostname(
                    client_socket, client_address, command["payload"]["hostname"]
                )
            elif command["header"] == "discover":

                self.log_request(
                    f">>> Client {client_address}: {command['header'].upper()}\n---\n"
                )
                self.client_discover(
                    client_socket, client_address
                )   
            else:
                self.log_request(
                    f">>> Client {client_address}: Unknown command {command}"
                )

    def process_server_command(self, command):
        """Process a command received from the server console

        Args:
            command (str): The command to process
        """
        with self.lock:
            if self.is_running:
                command_parts = command.split()
                self.log(f"\nServer$ {command}")

                if not command:
                    self.log("Server command cannot be blank!")
                elif command_parts[0] == "discover":
                    self.server_discover(command_parts[1])
                elif command_parts[0] == "ping":
                    self.server_ping(command_parts[1])
                elif command_parts[0] == "shutdown":
                    self.shutdown()
                else:
                    self.log(f"Unknown server command: {command}")
            else:
                self.log("Start the server before sending commands!")

    def publish(self, client_address, fname):
        """Handle publish request from client

        Args:
            client_address (tuple[str, int]): The client's address
            lname (str): file's name on the client's machine
            fname (list): list of file names on the server
        """
        if client_address in self.clients:
            self.clients[client_address]["files"].extend(fname)
            file_names_str = ', '.join([f'"{file}"' for file in fname])
            self.log(
                f"Files {file_names_str} published by {client_address}"
            )
        else:
            self.log(f"Unknown client {client_address}")

    def fetch(self, client_socket, requesting_client, fname):
        """Handle fetch request from client

        Args:
            client_socket (socket): The client' socket
            requesting_client (tuple[str, int]): Client's address
            fname (str): file's name on the server
        """
        found_client: list[tuple[tuple[str, int], Any]] = [
            (addr, data)
            for addr, data in self.clients.items()
            if any(file == fname for file in data["files"])
            and addr != requesting_client
        ]

        if len(found_client) > 0:
            response_data = {
                "header": "fetch",
                "type": 1,
                "payload": {
                    "success": True,
                    "message": f"File '{fname}' found",
                    "fname": fname,
                    "available_clients": [
                        {
                            "hostname": data["hostname"],
                            "address": addr,
                        }
                        for (addr, data) in found_client
                    ],
                },
            }
            response = json.dumps(response_data)
            client_socket.send(response.encode("utf-8", "replace"))
        else:
            response_data = {
                "header": "fetch",
                "type": 1,
                "payload": {
                    "success": False,
                    "message": f"File '{fname}' not found",
                    "fname": fname,
                    "available_clients": [],
                },
            }
            response = json.dumps(response_data)
            client_socket.send(response.encode("utf-8", "replace"))

    def set_hostname(self, client_socket, client_address, hostname: str):
        """Set the hostname for a client

        Args:
            client_socket (socket): The client' socket
            client_address (tuple[str, int]): The client's address
            hostname (str): The hostname to set
        """
        if client_address in self.clients:
            if " " in hostname:
                response = json.dumps(
                    {
                        "header": "sethost",
                        "type": 1,
                        "payload": {
                            "success": False,
                            "message": "Hostname cannot contain spaces",
                            "hostname": hostname,
                            "address": client_address,
                        },
                    }
                )
                client_socket.send(response.encode("utf-8", "replace"))
            else:
                if not any(
                    data["hostname"] == hostname
                    for addr, data in self.clients.items()
                    if addr != client_address
                ):
                    self.clients[client_address]["hostname"] = hostname
                    response_data = {
                        "header": "sethost",
                        "type": 1,
                        "payload": {
                            "success": True,
                            "message": f"Hostname '{hostname}' "
                            f"set for {client_address}",
                            "hostname": hostname,
                            "address": client_address,
                        },
                    }
                    response = json.dumps(response_data)
                    self.log(response_data["payload"]["message"])
                    client_socket.send(response.encode("utf-8", "replace"))
                else:
                    response_data = {
                        "header": "sethost",
                        "type": 1,
                        "payload": {
                            "success": False,
                            "message": f"Hostname '{hostname}' already in use",
                            "hostname": hostname,
                            "address": client_address,
                        },
                    }
                    response = json.dumps(response_data)
                    self.log(response_data["payload"]["message"])
                    client_socket.send(response.encode("utf-8", "replace"))
        else:
            response_data = {
                "header": "sethost",
                "type": 1,
                "payload": {
                    "success": False,
                    "message": f"Unknown client {client_address}",
                    "hostname": hostname,
                    "address": client_address,
                },
            }
            response = json.dumps(response_data)
            self.log(response_data["payload"]["message"])
            client_socket.send(response.encode("utf-8", "replace"))

    def server_discover(self, hostname):
        """Discover published files with the given hostname

        Args:
            hostname (str): The hostname to search for
        """
        found_client = None
        for addr, data in self.clients.items():
            if data["hostname"] == hostname:
                found_client = addr
                break
        found_files = [
            data["files"]
            for _, data in self.clients.items()
            if data["hostname"] == hostname
        ]
        
        if found_files:
            found_files = found_files[0]
        else:
            found_files = []

        if len(found_files) > 0:
            response = f"Files on hosts with hostname '{hostname}':\n"
            file_names_str = ', '.join([f'"{file}"' for file in found_files])
            response += file_names_str

        elif found_client:
            response = f"No files on hosts with hostname '{hostname}'\n"
        else:
            response = f"No hosts found with hostname '{hostname}'"

        self.log(response)

    def server_ping(self, hostname):
        """Ping a client with the given hostname

        Args:
            hostname (str): The hostname to ping
        """
        found_client = None
        for addr, data in self.clients.items():
            if data["hostname"] == hostname:
                found_client = addr
                break

        if found_client:
            self.log(f"Pinging {hostname}...")
            response_data = self.send_ping(addr)
            self.log(response_data)
        else:
            self.log(f"Unknown client '{hostname}'")

    def send_ping(self, client_address):
        """Send a ping request to a client

        Args:
            client_address (tuple[str, int]): the client's address

        Returns:
            str: Result to print to the console
        """
        if client_address in self.clients:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client_socket.connect(client_address)
                ping_message = {"header": "ping", "type": 0}
                client_socket.send(json.dumps(ping_message).encode("utf-8", "replace"))

                ready, _, _ = select.select([client_socket], [], [], 8.0)

                if ready:
                    client_socket.recv(1024).decode("utf-8", "replace")
                    return (
                        f"Client status: Alive\n"
                    )
                else:
                    return "Client status: Not Alive\nRTT: None"
            except Exception as e:
                return f"Error pinging client: {e}"
            finally:
                client_socket.close()
        else:
            return f"Unknown client {client_address}"

    def client_discover(self, client_socket, requesting_client):
        """Handle discovery request from client

        Args:
            client_socket (socket): The client' socket
            requesting_client (tuple[str, int]): Client's address
        """
        client_address = client_socket.getpeername()
        client_file = self.clients[client_address]["files"]
        all_file_names = []
        seen_files = set()

        for client_info in self.clients.values():
            for file_name in client_info["files"]:
                if file_name not in seen_files and file_name not in client_file:
                    all_file_names.append(file_name)
                    seen_files.add(file_name)
        response_data = {
            "header": "discover",
            "type": 1,
            "payload": {
                "success": True,
                "message": "Discover list: ",
                "fname": [all_file_names],
            },
        }
        response = json.dumps(response_data)
        client_socket.send(response.encode("utf-8", "replace"))
    
    def shutdown(self):
        """Shutdown the server"""
        self.log("Shutting down the server...")
        self.is_running = False
        try:
            # Create a dummy connection to unblock the server from accept,
            # and then close the server socket
            dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dummy_socket.connect((self.host, self.port))
            dummy_socket.close()
        except Exception as e:
            if self.is_running:
                self.log(f"Error shutdown the server: {e}")
        sys.exit(0)


# if __name__ == "__main__":
#     server = FileServer("localhost", 5555)
#     server.start()
