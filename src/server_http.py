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

body_content = ""

def buildPage(method, path, destination):
    if(method.decode('ascii') == 'GET'):
        pagePath = '../html' + path.decode('ascii')
        print("caminho: ", pagePath)
        try:
            with open(pagePath, 'rb') as f:
                destination.sendfile(f,0)
                f.close()
        except FileNotFoundError:
            destination.sendfile(open('../html/error404.html', 'rb'), 0)
        except IsADirectoryError:
            destination.sendfile(open('../html/error400.html', 'rb'), 0)
    elif(method.decode('ascii') == 'POST'):
        destination.sendfile(open('../html/error405.html', 'rb'), 0)
    else:
        destination.send(b'A failure occurried')

    return

def main():
    try:

        while True:
            client_sokt, addr = sokt.accept() #Wait for incomming conection
            received_requisition = client_sokt.recv(1500) #Receive requisition from client (1500 bytes is the typical network layer limit)
            print ("Received data: \n", received_requisition) #Shows the requisition on console

            method, path, other = received_requisition.split(b' ', 2)
            if other.startswith(b'HTTP/1.1'):
                client_sokt.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Lenght: 1024\r\n\r\n')
                buildPage(method, path, client_sokt)
            else:
                print('Invalid HTTP request')
                client_sokt.send(default_msg)
            client_sokt.close()
        
        sokt.close()
        print('Conection closed')
        sys.exit(0)
            




    except KeyboardInterrupt: #In case of manual interrupt
        sokt.close()
        print('The conection has been keyboardly terminated')
        sys.exit(0)

if __name__ == '__main__':
    main()