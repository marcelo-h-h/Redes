#!/usr/bin/python3
# -*- encoding: utf-8 -*-

import socket
import sys

server_address = ('', 8000)
sokt = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Set family and type of socket
sokt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #Set socket option
sokt.bind(server_address) #Bind the socket to a local address
sokt.listen(5) #Enable conections with max of 5 reconnect attemps

default_msg = b""" 
HTTP/1.1 200 OK
Content-Type: text/html

<html>
<body>
<b>Default</b>
</body>
</html>

""" #Default HTTP Header + Hello World page


try:

    while True:
        client_sokt, addr = sokt.accept() #Wait for incomming conection
        received_requisition = client_sokt.recv(2000) #Receive requisition from client
        print (")Received data: \n", received_requisition) #Shows the requisition on console

        method, path, other = received_requisition.split(b' ', 2)
        if other.startswith(b'HTTP/1.1'):
            body_content = b"""
            <html>
            <body>
            <b>Conection Sucefull</b>
            </body>
            </html>
            """
            client_sokt.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Lenght: %d\r\n\r\n' % len(body_content))
            client_sokt.send(body_content)

        else:
            print('Invalid HTTP request')
            client_sokt.send(default_msg)
    
    sokt.close()
    print('Conection closed')
    sys.exit(0)
        




except KeyboardInterrupt: #In case of manual interrupt
    sokt.close()
    print('The conection has been keyboardly terminated')
    sys.exit(0)
