import socket

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('localhost', 8000)
client_socket.connect(server_address)

request_header = b'GET /home.html HTTP/1.1\r\nHost: localhost:8000\r\nConnection: keep-alive\r\nAccept: text/html,application/xhtml+xml,application/xml;\r\nAccept-Encoding: gzip, deflate, br\r\nAccept-Language: pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7\r\n\r\n'
client_socket.send(request_header)

response = ''
while True:
    recv = client_socket.recv(1024)
    if not recv:
        break
    response += recv.decode("utf-8")
    print (response)
client_socket.close()  
