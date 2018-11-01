#
import socket

id = ''
port = 8000
bind_addr = (ip,port)
server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
server.bind(bind_addr)
server.listen(1)
print("Start listening at: ",ip,":",port)
client_sokt, client_addr = sokt.accept()
print("Connected: ", client_sokt, ":", client_addr)
