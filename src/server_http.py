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

def buildPage(method, path, destination):
    if(method.decode('ascii') == 'GET'):
        pagePath = '../html' + path.decode('ascii')
        try:
            with open(pagePath, 'rb') as f:
                destination.sendfile(f,0)
        except FileNotFoundError:
            destination.sendfile(open('../html/error404.html', 'rb'), 0)
        except IsADirectoryError:
            destination.sendfile(open('../html/error400.html', 'rb'), 0)
    else:
        destination.send(b'A failure occurried')

def main():
    try:

        while True:
            client_sokt, addr = sokt.accept() #Wait for incomming conection
            received_requisition = client_sokt.recv(1500) #Receive requisition from client (1500 bytes is the typical network layer limit)
            print ("Received data: \n", received_requisition) #Shows the requisition on console

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
            # client_sokt.send(body_content)
            # with open('html/home.html', 'rb') as f:
                    #client_sokt.sendfile(f, 0)
                buildPage(method, path, client_sokt)
                #client_sokt.sendfile(buildPage(method, path), 0)

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

if __name__ == '__main__':
    main()