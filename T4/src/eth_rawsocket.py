#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#


import socket
import asyncio
import struct
import time

ETH_P_ALL = 0x0003
ETH_P_IP  = 0x0800
DATAGRAM_TIMEOUT = 15 #(RFC0791)


ICMP = 0x01  # https://en.wikipedia.org/wiki/List_of_IP_protocol_numbers


# Coloque aqui o endereço de destino para onde você quer mandar o ping
dest_ip = '10.0.2.2'

# Coloque abaixo o endereço IP do seu computador na sua rede local
src_ip = '10.0.2.15'

# Coloque aqui o nome da sua placa de rede
if_name = 'enp0s3'

# Coloque aqui o endereço MAC do roteador da sua rede local (arp -a | grep _gateway)
dest_mac = '52:54:00:12:35:02'

# Coloque aqui o endereço MAC da sua placa de rede (ip link show dev wlan0)
src_mac = '08:00:27:a3:77:d1'

FLAGS_MOREFRAGS = 1<<0


class Package:
    def __init__(self):
        self.offsets = set()
        self.timer = None
        self.buffer = bytearray()
        self.data_length = 0
        self.total_data_length = None

pacotes = {}


def ip_addr_to_bytes(addr):
    return bytes(map(int, addr.split('.')))

def mac_addr_to_bytes(addr):
    return bytes(int('0x'+s, 16) for s in addr.split(':'))

def addr2str(addr):
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)

def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))



def send_eth(fd, datagram, protocol):
    eth_header = mac_addr_to_bytes(dest_mac) + \
        mac_addr_to_bytes(src_mac) + \
        struct.pack('!H', protocol)
    fd.send(eth_header + datagram)


#Interpreta o cabeçalho IPV4
def handle_ipv4_header(packet):
    version = packet[0] >> 4
    ihl = packet[0] & 0xf
    assert version == 4
    identifier = packet[4:6]
    flags = packet[6] >> 5
    offset = (int.from_bytes(packet[6:8], byteorder='big', signed=False) & 0x1fff) << 3
    src_addr = addr2str(packet[12:16])
    segment = packet[4*ihl:]
    return identifier, flags, offset, src_addr, segment



ip_pkt_id = 0
def send_ip(fd, msg, protocol):
    global ip_pkt_id
    ip_header = bytearray(struct.pack('!BBHHHBBH',
                            0x45, 0,
                            20 + len(msg),
                            ip_pkt_id,
                            0,
                            15,
                            protocol,
                            0) +
                          ip_addr_to_bytes(src_ip) +
                          ip_addr_to_bytes(dest_ip))
    ip_header[10:12] = struct.pack('!H', calc_checksum(ip_header))
    ip_pkt_id += 1
    send_eth(fd, ip_header + msg, ETH_P_IP)

def set_timer(pacote):
    if pacote.timer == None:
        pacote.timer = time.time()

def send_ping(fd):
    print('enviando ping')
    # Exemplo de pacote ping (ICMP echo request) com payload grande
    msg = bytearray(b"\x08\x00\x00\x00" + 2*b"\xba\xdc\x0f\xfe")
    msg[2:4] = struct.pack('!H', calc_checksum(msg))

    send_ip(fd, msg, ICMP)

    asyncio.get_event_loop().call_later(3, send_ping, fd)

def check_timeouts():
    removable = set()
    for id_pacote in pacotes:
        if time.time() - pacotes[id_pacote].timer > DATAGRAM_TIMEOUT:
            removable.add(id_pacote)
        for id in removable:
            del pacotes[id]
    asyncio.get_event_loop().call_later(1,check_timeouts)

def network_processment(packet):
    print('Processando o pacote IP')
    identifier, flags, offset, src_addr, segment = handle_ipv4_header(packet)
    if(src_addr == dest_ip): #Filtrando apenas o tráfego ao roteador que recebe o ping para fins de melhor visualização
        if (flags & FLAGS_MOREFRAGS) == FLAGS_MOREFRAGS or offset != 0: #Pacote fragmentado
            print('recebido fragmento de %d bytes' % len(packet))
            id_package = (src_addr, identifier)
            if id_package not in pacotes:
                pacotes[id_package] = pacote = Package()
            else:
                pacote = pacotes[id_package]
            if pacote.timer is None:
                set_timer(pacote)
            #manter um conjunto de offsets para poder ignorar pacotes duplicados
            if offset not in pacote.offsets:
                if offset != 0 and (flags & FLAGS_MOREFRAGS) == 0:  #Caso seja o ultimo pacote
                    print('Ultimo fragmento recebido')
                    pacote.total_data_length = offset + len(segment)
                pacote.data_length += len(segment)
                pacote.offsets.add(offset)

                while len(pacote.buffer) < offset + len(segment):
                    pacote.buffer.append(0)
                pacote.buffer[offset:offset+len(segment)] = segment
                print('Adicionado o pacote com comprimento: ', len(segment), 'ao buffer, que passa a ter ', len(pacote.buffer))

                if pacote.total_data_length == pacote.data_length:  #Caso já tenha recebido todos os fragmentos
                    print('O buffer está completo, informações do pacote recebido:')
                    print('\tFonte:', src_addr)
                    print('\tIdentificador', identifier)
                    print('\ttamanho remontado:', len(pacote.buffer))
             #       print('\tConteúdo: ', pacote.buffer)

                    del pacotes[id_package]
                    print('\n')

        else: #Pacote não fragmentado
            print('Não fragmentado')
            print('Informações do pacote:')
            print('\tFonte: ', src_addr)
            print('\tIdentificador', identifier)
            print('\tTamanho dos dados: ', len(segment))
          #  print('\tConteúdo: ', segment)
            print('\n')





def raw_recv(fd):
    frame = fd.recv(12000)
    #Realiza as verificações a partir do cabeçalho eth, verificando se o pacote está realmente
    #endereçado para uma placa de rede deste computador, indicada em src_mac e se o protocolo é
    #o protocolo ETH_P_IP
    if(frame[:6] == mac_addr_to_bytes(src_mac)) and (struct.unpack('!H', frame[12:14])[0] == ETH_P_IP):
        print('recebido quadro de %d bytes' % len(frame))
        network_processment(frame[14:])
        
    #print('começo', frame[:14])


def calc_checksum(segment):
    if len(segment) % 2 == 1:
        # se for ímpar, faz padding à direita
        segment += b'\x00'
    checksum = 0
    for i in range(0, len(segment), 2):
        x, = struct.unpack('!H', segment[i:i+2])
        checksum += x
        while checksum > 0xffff:
            checksum = (checksum & 0xffff) + 1
    checksum = ~checksum
    return checksum & 0xffff


if __name__ == '__main__':
    # Ver http://man7.org/linux/man-pages/man7/packet.7.html
    fd = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    fd.bind((if_name, 0))

    loop = asyncio.get_event_loop()
    loop.add_reader(fd, raw_recv, fd)
    asyncio.get_event_loop().call_later(1, send_ping, fd)
    asyncio.get_event_loop().call_soon(check_timeouts)

loop.run_forever()