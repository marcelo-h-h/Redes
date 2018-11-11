#sudo ip link set lo mtu 1500
#Quando chegar o primeiro fragmento, inicia um timer
#Se demorar mais de 30 segundos, descarta tudo que recebeu e desiste de remontar o datagrama


import socket
import asyncio
import struct
import sys

FLAGS_MOREFRAGS = 1<<0

ETH_P_IP = 0x0800

class Package:
    def __init__(self):
        self.offsets = set()
        self.timer = None
        self.buffer = bytearray()
        self.data_length = 0
        self.total_data_length = None

pacotes = {}



# Coloque aqui o endereço de destino para onde você quer mandar o ping
dest_addr = '192.168.0.1'

def addr2str(addr):
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)

def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))

#Interpreta o cabeçalho IPV4
def handle_ipv4_header(packet):
    version = packet[0] >> 4
    ihl = packet[0] & 0xf
    assert version == 4
    total_length = packet[2:4]
    identifier = packet[4:6]
    flags = packet[6] >> 5
    offset = (int.from_bytes(packet[6:8], byteorder='big', signed=False) & 0x1fff) << 3
    src_addr = addr2str(packet[12:16])
    dst_addr = addr2str(packet[16:20])
    segment = packet[4*ihl:]
    return total_length, identifier, flags, offset, src_addr, dst_addr, segment

def send_ping(send_fd):
    print('enviando ping')
    # Exemplo de pacote ping (ICMP echo request) com payload grande
    msg = bytearray(b"\x08\x00\x00\x00" + 5000*b"\xba\xdc\x0f\xfe")
    msg[2:4] = struct.pack('!H', calc_checksum(msg))
    send_fd.sendto(msg, (dest_addr, 0))

    asyncio.get_event_loop().call_later(3, send_ping, send_fd)

def raw_recv(recv_fd):
    packet = recv_fd.recv(12000)
    total_length, identifier, flags, offset, src_addr, dst_addr, segment = handle_ipv4_header(packet)

    if (flags & FLAGS_MOREFRAGS) == FLAGS_MOREFRAGS or offset != 0: #Pacote fragmentado
        print('recebido fragmento de %d bytes' % len(packet))
        id_package = (src_addr, identifier)
        if id_package not in pacotes:
            pacotes[id_package] = pacote = Package()
        else:
            pacote = pacotes[id_package]
        #manter um conjunto de offsets para poder ignorar pacotes duplicados
        if src_addr == dest_addr and offset not in pacote.offsets:
            if offset != 0 and (flags & FLAGS_MOREFRAGS) == 0:  #Caso seja o ultimo pacote
                print('Ultimo pacote recebido')
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
                print('\ttamanho remontado:', len(pacote.buffer))
                print('\tFonte: ', src_addr)
                print('\tTamanho dos dados: ', len(segment))
                del pacotes[id_package]
                

            

            #TODO
            #set_timer(package)


    else:
        if(src_addr == dest_addr):
            print('Não fragmentado')
            print('Informações do pacote:')
            print('\tFonte: ', src_addr)
            print('\tTamanho dos dados: ', len(segment))

        




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
    # Ver http://man7.org/linux/man-pages/man7/raw.7.html
    send_fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    # Para receber existem duas abordagens. A primeira é a da etapa anterior
    # do trabalho, de colocar socket.IPPROTO_TCP, socket.IPPROTO_UDP ou
    # socket.IPPROTO_ICMP. Assim ele filtra só datagramas IP que contenham um
    # segmento TCP, UDP ou mensagem ICMP, respectivamente, e permite que esses
    # datagramas sejam recebidos. No entanto, essa abordagem faz com que o
    # próprio sistema operacional realize boa parte do trabalho da camada IP,
    # como remontar datagramas fragmentados. Para que essa questão fique a
    # cargo do nosso programa, é necessário uma outra abordagem: usar um socket
    # de camada de enlace, porém pedir para que as informações de camada de
    # enlace não sejam apresentadas a nós, como abaixo. Esse socket também
    # poderia ser usado para enviar pacotes, mas somente se eles forem quadros,
    # ou seja, se incluírem cabeçalhos da camada de enlace.
    # Ver http://man7.org/linux/man-pages/man7/packet.7.html
    recv_fd = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_IP))

    loop = asyncio.get_event_loop()
    loop.add_reader(recv_fd, raw_recv, recv_fd)
    asyncio.get_event_loop().call_later(1, send_ping, send_fd)
    loop.run_forever()