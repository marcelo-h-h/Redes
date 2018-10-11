#!/usr/bin/python3
#
# Antes de usar, execute o seguinte comando para evitar que o Linux feche
# as conexões TCP abertas por este programa:
#
# sudo iptables -I OUTPUT -p tcp --tcp-flags RST RST -j DROP
#

import asyncio
import socket
import struct
import os

FLAGS_FIN = 1<<0
FLAGS_SYN = 1<<1
FLAGS_RST = 1<<2
FLAGS_ACK = 1<<4

MSS = 1460 #tamanho máximo do pacote visto que 40bytes são dos cabeçalhos IP e TCP

class Conexao:
    def __init__(self, id_conexao, seq_no, ack_no):
        self.id_conexao = id_conexao
        self.seq_no = seq_no
        self.ack_no = ack_no
        self.send_queue = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n" + 20000 * b"hello pombo\n"
conexoes = {}



def addr2str(addr): #traduz para um endereço entendível pelo usuário
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)

def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))

def handle_ipv4_header(packet): #extrai informações necessárias do cabeçalho da camada de rede
    version = packet[0] >> 4 #verifica se é a versão 4(ipv4)
    ihl = packet[0] & 0xf #verfica o tamanho do cabeçado (vem em multiplos de 4 bytes)
    assert version == 4 #Erro se nao for a versão 4
    src_addr = addr2str(packet[12:16])
    dst_addr = addr2str(packet[16:20])
    segment = packet[4*ihl:] #corta o cabeçalho do pacote
    return src_addr, dst_addr, segment


def make_synack(src_port, dst_port, ack_no): #pacote para aceitar conexão
    return struct.pack('!HHIIHHHH', src_port, dst_port, 0,
                       ack_no, (5<<12)|FLAGS_ACK|FLAGS_SYN,
                       1024, 0, 0) #põe se o tamanho do buffer como 1024 mas ele está vazio


def calc_checksum(segment):
    checksum = 0
    for i in range(0, len(segment), 2): #pulando de 2 em 2 bytes
        x, = struct.unpack('!H', segment[i:i+2]) #decifra um número em big endian de 2 bytes
        checksum += x
        while checksum > 0xffff: #se estourar o número máximo
            checksum = (checksum & 0xffff) + 1
    checksum = ~checksum
    return checksum & 0xffff

def fix_checksum(segment, src_addr, dst_addr):
    pseudohdr = str2addr(src_addr) + str2addr(dst_addr) + \
        struct.pack('!HH', 0x0006, len(segment))
    seg = bytearray(segment)
    seg[16:18] = b'\x00\x00' #por precaução
    seg[16:18] = struct.pack('!H', calc_checksum(pseudohdr + seg))
    return bytes(seg)

def send_next(fd, conexao):
    payload = conexao.send_queue[:MSS]
    conexao.send_queue = conexao.send_queue[MSS:]

    (dst_addr, dst_port, src_addr, src_port) = conexao.id_conexao

    segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no,
                          conexao.ack_no, (5<<12)|FLAGS_ACK,
                          1024, 0, 0) + payload

    conexao.seq_no = (conexao.seq_no + len(payload)) & 0xffffffff #limitar o tamanho a 32bits

    segment = fix_checksum(segment, src_addr, dst_addr)
    fd.sendto(segment, (dst_addr, dst_port))

    if conexao.send_queue != b"":
        asyncio.get_event_loop().call_later(.1, send_next, fd, conexao)



def timer_test(src_addr, src_port):
    print('5 segundos desde que aceitamos a conexão de %s:%d' %
          (src_addr, src_port))



def raw_recv(fd): #função principal do programa
    packet = fd.recv(12000) #um número grande para um limite superior de bytes
    src_addr, dst_addr, segment = handle_ipv4_header(packet) #remove os endereços de origem e destino do cabeçalho do pacote, retorna só o segmento
    src_port, dst_port, seq_no, ack_no, \
        flags, window_size, checksum, urg_ptr = \
        struct.unpack('!HHIIHHHH', segment[:20])

    id_conexao = (src_addr, src_port, dst_addr, dst_port)

    if dst_port != 7000: #recebe pacotes apenas na porta 7000, se não for, nosso programa não tem nada a ver com isso
        return

    if (flags & FLAGS_SYN) == FLAGS_SYN: #há tentativa de estabelecer conexão
        print('%s:%d -> %s:%d (seq=%d)' % (src_addr, src_port,
                                           dst_addr, dst_port, seq_no))

        conexoes[id_conexao] = conexao = Conexao(id_conexao=id_conexao,
                                                 seq_no=struct.unpack('I', os.urandom(4))[0],
                                                 ack_no=seq_no + 1) #armazena os dados da conexão para poder estabelecer os handshakes

        fd.sendto(fix_checksum(make_synack(dst_port, src_port, conexao.seq_no, conexao.ack_no),
                               src_addr, dst_addr),
                  (src_addr, src_port)) #devolve synack para aceitar a conexão

        conexao.seq_no += 1

        asyncio.get_event_loop().call_later(.1, send_next, fd, conexao)


fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
loop = asyncio.get_event_loop()
loop.add_reader(fd, raw_recv, fd) #tratar dados disponíveis pra leitura
loop.run_forever()