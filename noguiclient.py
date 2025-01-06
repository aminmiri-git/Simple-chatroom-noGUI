import socket
import threading
import os
import struct

try:
    import androidhelper
    IS_ANDROID = True
    droid = androidhelper.Android()
    received_dir = droid.getExternalStorageDirectory().result + "/received_files"
    os.makedirs(received_dir, exist_ok=True)
except ImportError:
    IS_ANDROID = False
    received_dir = "received_files"
    if not os.path.exists(received_dir):
        os.makedirs(received_dir)

class Client:
    def __init__(self, client_name, server_address):
        self.client_name = client_name
        self.server_address = server_address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect(self.server_address)
            self.socket.sendall(bytes(self.client_name, 'utf-8'))
        except ConnectionRefusedError:
            print("Connection to server refused. Make sure the server is running.")
            exit()
        except Exception as e:
            print(f"An error occurred during connection: {e}")
            exit()

    def send_message(self, message):
        try:
            self.socket.sendall(bytes(message, 'utf-8'))
        except Exception as e:
            print(f"Error sending message: {e}")
            self.socket.close()
            exit()

    def send_file(self, file_path):
        if os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            try:
                self.socket.sendall(b"FILE:" + file_name.encode('utf-8'))
                self.socket.sendall(struct.pack(">I", file_size))
                with open(file_path, 'rb') as f:
                    self.socket.sendall(f.read())
                print(f"File '{file_name}' sent successfully.")
            except Exception as e:
                print(f"Error sending file: {e}")
                self.socket.close()
                exit()
        else:
            print("File not found.")

    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break

                if data.startswith(b"FILE:"):
                    file_name = data[5:].decode('utf-8', errors='ignore')
                    file_size_bytes = self.socket.recv(4)
                    file_size = struct.unpack(">I", file_size_bytes)[0]

                    file_data = b""
                    bytes_received = 0
                    while bytes_received < file_size:
                        remaining_bytes = file_size - bytes_received
                        chunk = self.socket.recv(min(4096, remaining_bytes))
                        if not chunk:
                            print("Connection closed during file transfer.")
                            break
                        file_data += chunk
                        bytes_received += len(chunk)

                    if bytes_received == file_size:
                        file_path = os.path.join(received_dir, file_name)
                        with open(file_path, 'wb') as f:
                            f.write(file_data)
                        print(f"File '{file_name}' received and saved to '{file_path}'.")
                    else:
                        print(f"File '{file_name}' transfer incomplete. Received {bytes_received} of {file_size} bytes.")

                else:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    print(decoded_data)
            except Exception as e:
                print(f"Error receiving messages: {e}")
                self.socket.close()
                break

def discover_server(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(2)

    message = b"DISCOVER_REQUEST"
    s.sendto(message, ('<broadcast>', port))

    try:
        data, (server_ip, _) = s.recvfrom(1024)
        if data == b"DISCOVER_RESPONSE":
            print(f"Server found at {server_ip}")
            return server_ip
    except socket.timeout:
        print("No server found.")
    except Exception as e:
        print(f"Error during discovery: {e}")
    finally:
        s.close()
    return None

def main():
    client_name = input("Enter your name: ")
    server_ip = discover_server(8080)
    if server_ip:
        server_address = (server_ip, 8080)
        client = Client(client_name, server_address)
        threading.Thread(target=client.receive_messages, daemon=True).start()

        while True:
            message = input("Enter a message (or type 'send file' to send a file): ")
            if message.lower() == "send file":
                file_path = input("Enter the file path: ")
                client.send_file(file_path)
            else:
                client.send_message(message)
    else:
        print("Could not find server. Exiting.")

if __name__ == "__main__":
    main()