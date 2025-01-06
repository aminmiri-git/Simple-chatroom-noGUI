import os
import socket
import threading
import struct
from datetime import datetime

class Server:
    def __init__(self):
        self.users_table = {}
        self.server_address = (self.get_local_ip(), 8080)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(self.server_address)
        self.socket.listen(10)
        print(f"Server started on {self.server_address}")

        self.save_folder = "received_files"
        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder)

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def run(self):
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.bind(('', 8080))
        threading.Thread(target=self.handle_discovery, args=(discovery_socket,)).start()
        while True:
            connection, _ = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(connection,)).start()

    def handle_discovery(self, discovery_socket):
        while True:
            data, (client_ip, client_port) = discovery_socket.recvfrom(1024)
            if data == b"DISCOVER_REQUEST":
                discovery_socket.sendto(b"DISCOVER_RESPONSE", (client_ip, client_port))

    def handle_client(self, connection):
        try:
            client_name = connection.recv(64).decode('utf-8')
            self.users_table[connection] = client_name
            print(f"{self.get_time()} {client_name} joined the room!")

            while True:
                data = connection.recv(1024)
                if not data:
                    break

                if data.startswith(b"FILE:"):
                    self.handle_file_transfer(data, connection)
                else:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    self.broadcast_message(decoded_data, connection)
        except Exception as e:
            print(f"Error with a client: {e}")
        finally:
            if connection in self.users_table:
                client_name = self.users_table[connection]
                print(f"{self.get_time()} {client_name} left the room!")
                self.users_table.pop(connection, None)
            connection.close()

    def get_time(self):
        return datetime.now().strftime("%H:%M:%S")

    def broadcast_message(self, message, owner):
        for conn in self.users_table:
            if conn != owner:
                try:
                    conn.sendall(bytes(f"{self.get_time()} {self.users_table[owner]}: {message}", 'utf-8'))
                except Exception as e:
                    print(f"Error broadcasting message: {e}")

    def handle_file_transfer(self, data, connection):
        try:
            file_name = data[5:].decode('utf-8', errors='ignore')
            file_size_bytes = connection.recv(4)
            file_size = struct.unpack(">I", file_size_bytes)[0]

            file_data = b""
            while len(file_data) < file_size:
                file_data += connection.recv(min(4096, file_size - len(file_data)))

            self.save_file(file_name, file_data)
            self.broadcast_file(file_name, file_data, connection)
        except Exception as e:
            print(f"Error receiving file: {e}")

    def save_file(self, file_name, file_data):
        try:
            file_path = os.path.join(self.save_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(file_data)
            print(f"File '{file_name}' saved to {file_path}.")
        except Exception as e:
            print(f"Error saving file: {e}")

    def broadcast_file(self, file_name, file_data, owner):
        def send_file_to_client(conn, file_name, file_data):
            try:
                conn.sendall(b"FILE:" + file_name.encode('utf-8'))
                conn.sendall(struct.pack(">I", len(file_data)))
                conn.sendall(file_data)
            except Exception as e:
                print(f"Error sending file to {self.users_table.get(conn)}: {e}")
                try:
                    conn.close()
                    self.users_table.pop(conn, None)
                except:
                    pass

        for conn in self.users_table:
            if conn != owner:
                threading.Thread(target=send_file_to_client, args=(conn, file_name, file_data)).start()

if __name__ == "__main__":
    server = Server()
    server.run()