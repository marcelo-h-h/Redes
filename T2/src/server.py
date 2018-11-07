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
import random
import time

FLAGS_FIN = 1<<0
FLAGS_SYN = 1<<1
FLAGS_RST = 1<<2
FLAGS_ACK = 1<<4

MSS = 1460
BUFFER_SIZE = MSS * 5

TESTAR_PERDA_ENVIO = False


class Conexao:
    def __init__(self, id_conexao, seq_no, ack_no):
        self.id_conexao = id_conexao
        self.seq_no = seq_no
        self.ack_no = ack_no
        
        self.status = 0 #Define o status da conexão (0: Desconectado, 1: Conectando, 2: Conexão Estabelecida)

        self.rto = 3 #Até que o RTT seja medido com um segmento válido, deve ser atribuido 3. (RFC2988)
        self.srtt = None #Variável usada no cálculo do RTO
        self.rttvar = None #Variável usada no cálculo do RTO

        self.ssthreshold = 0xffffffff #Threshold para definir o maior valor de pacotes que pode estar em trânsito
        self.congest_window = MSS #Congestion window
        self.receiv_window = 0 #Client Window
        self.departure_time = None #Armazena o momento em que é enviado o payload nessa conexão
        self.buffer = bytes()

        self.send_queue = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 146000\r\n\r\n" + 146000 * b"a"
conexoes = {}



def addr2str(addr):
    return '%d.%d.%d.%d' % tuple(int(x) for x in addr)

def str2addr(addr):
    return bytes(int(x) for x in addr.split('.'))

#Ativa o timer da conexão para medir timeout
def set_timer(conexao):
    if conexao.departure_time == None:
        conexao.departure_time = time.time()
    else:
        conexao.departure_time == False

def set_congest_window(conexao):
    if conexao.departure_time != False and conexao.congest_window < conexao.ssthreshold:
        sent_size = min(conexao.congest_window, conexao.receiv_window, len(conexao.send_queue))
        conexao.congest_window += min(sent_size, MSS)
    else:
        conexao.ssthreshold = max(congest_window/2, 2*MSS)
        conexao.congest_window = MSS

def set_rto(conexao): #Calculo do RTO de acordo com RFC2988
    if conexao.departure_time != False and conexao.departure_time is not None:
        r = time.time() - conexao.departure_time

        #Quando calculando pela 1ª vez
        if not conexao.srtt and not conexao.rttvar:
            conexao.srtt = r
            conexao.rttvar = r/2
        #Caso já tenha sido previamente calculado alguma vez
        else:
            conexao.rttvar = (3/4) * conexao.rttvar + 1/4 * abs(conexao.srtt - r)
            conexao.srtt = (7/8) * conexao.srtt + 1/8 * r
    conexao.rto = conexao.srtt + max(3, 4*conexao.rttvar)
    if conexao.rto < 1:
        conexao.rto = 1;
    conexao.departure_time = None

#Interpreta o cabeçalho IPV4
def handle_ipv4_header(packet):
    version = packet[0] >> 4
    ihl = packet[0] & 0xf
    assert version == 4
    src_addr = addr2str(packet[12:16])
    dst_addr = addr2str(packet[16:20])
    segment = packet[4*ihl:]
    return src_addr, dst_addr, segment

#Prepara o pacote vazio com ACK
def make_ack(src_port, dst_port, seq_no, ack_no, window_size): #Prepare ack packet
    return struct.pack('!HHIIHHHH', src_port, dst_port, seq_no,
                       ack_no, (5<<12)|FLAGS_ACK,
                       window_size, 0, 0)

#Prepara o pacote vazio com SYN + ACK
def make_synack(src_port, dst_port, seq_no, ack_no, window_size): #Prepare Synack packet
    return struct.pack('!HHIIHHHH', src_port, dst_port, seq_no,
                       ack_no, (5<<12)|FLAGS_ACK|FLAGS_SYN,
                       window_size, 0, 0)

#Prepara o pacote vazio com FIN + ACk
def make_finack(src_port, dst_port, seq_no, ack_no, window_size): #Prepare Finack packet
    return struct.pack('!HHIIHHHH', src_port, dst_port, seq_no,
                       ack_no, (5<<12)|FLAGS_ACK|FLAGS_FIN,
                       window_size, 0, 0)

#Calcula o checksum
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

#Define o campo de checksum dentro do segmento
def fix_checksum(segment, src_addr, dst_addr):
    pseudohdr = str2addr(src_addr) + str2addr(dst_addr) + \
        struct.pack('!HH', 0x0006, len(segment))
    seg = bytearray(segment)
    seg[16:18] = b'\x00\x00'
    seg[16:18] = struct.pack('!H', calc_checksum(pseudohdr + seg))
    return bytes(seg)

def send_next(fd, conexao):
    #Parse nos dados da conexão
    (dst_addr, dst_port, src_addr, src_port) = conexao.id_conexao

     #Prepara o payload com os primeiros dados na fila com um limite de encher a janela de congestionamento
    payload = conexao.send_queue[:conexao.congest_window]

    set_timer(conexao)
    #Empacota e envia os dados advindos da fila de envio da conexão, com o tamanho máximo permitido até preencher um buffer correspondente à janela
    for i in range(0, min(conexao.congest_window, conexao.receiv_window, len(conexao.send_queue)),MSS):
        data = payload[i:i+MSS]
        segment = struct.pack('!HHIIHHHH', src_port, dst_port, conexao.seq_no+i,
                            conexao.ack_no, (5<<12)|FLAGS_ACK,
                            BUFFER_SIZE-len(conexao.buffer), 0, 0) + data
        segment = fix_checksum(segment, src_addr, dst_addr)
        fd.sendto(segment, (dst_addr, dst_port))

    #Roda a função novamente, verificando se precisa enviar os pacotes de novo(não recebeu acks) ou os próximos
    conexao.send_callback = asyncio.get_event_loop().call_later(conexao.rto, send_next, fd, conexao)
          
        
def raw_recv(fd):
    packet = fd.recv(12000)
    src_addr, dst_addr, segment = handle_ipv4_header(packet)
    src_port, dst_port, seq_no, ack_no, \
        flags, window_size, checksum, urg_ptr = \
        struct.unpack('!HHIIHHHH', segment[:20])

    id_conexao = (src_addr, src_port, dst_addr, dst_port)

    if dst_port != 8000:
        return

    payload = segment[4*(flags>>12):]

    if (flags & FLAGS_SYN) == FLAGS_SYN and id_conexao not in conexoes:
        print('%s:%d -> %s:%d (seq=%d)' % (src_addr, src_port,
                                           dst_addr, dst_port, seq_no))
        print('SYNACK enviado')

        conexoes[id_conexao] = conexao = Conexao(id_conexao=id_conexao,
                                                 seq_no=struct.unpack('I', os.urandom(4))[0],
                                                 ack_no=seq_no + 1)
        set_timer(conexao)

        fd.sendto(fix_checksum(make_synack(dst_port, src_port, conexao.seq_no, conexao.ack_no, BUFFER_SIZE),
                               src_addr, dst_addr),
                  (src_addr, src_port))

        conexao.seq_no += 1
        conexao.receiv_window = window_size

    elif id_conexao in conexoes: #A conexão já existe na lista de conexões (não é nova)
        conexao = conexoes[id_conexao]

        if len(conexao.buffer) + len(payload) <= BUFFER_SIZE: #Caso o tamanho do buffer não seja excedido
            conexao.buffer += payload

        conexao.receiv_window = window_size
        conexao.ack_no += len(payload)
        sent_size = min(conexao.congest_window, conexao.receiv_window, len(conexao.send_queue))

        #Caso a conexão receba um FIN do cliente, envia o finack e termina a conexão
        if (flags & FLAGS_FIN) == FLAGS_FIN:
            fd.sendto(fix_checksum(make_finack(dst_port, src_port, conexao.seq_no, conexao.ack_no+1, BUFFER_SIZE-len(conexao.buffer)),
                                   src_addr, dst_addr), (src_addr, src_port))
            conexao.status = 2
            print('Enviado finack\n')

        #Quando recebe um ack durante o estabelecimento da conexão (ACK para o SYNACK), muda para conexao estabelecida e calcula o primeiro RTO
        if (flags & FLAGS_ACK) == FLAGS_ACK and conexao.status == 0:
            conexao.status = 1
            set_rto(conexao)

        elif conexao.status == 1:
            if (flags & FLAGS_ACK) == FLAGS_ACK and conexao.seq_no + sent_size == ack_no:
                set_rto(conexao)
                set_congest_window(conexao)
                conexao.seq_no += sent_size
                conexao.send_queue = conexao.send_queue[sent_size:]

                conexao.send_callback.cancel()

                if conexao.send_queue != b'':
                    conexao.send_callback = asyncio.get_event_loop().call_soon(send_next, fd, conexao)
            elif payload != b'': 
                fd.sendto(fix_checksum(make_ack(dst_port, src_port, conexao.seq_no, conexao.ack_no, BUFFER_SIZE-len(conexao.buffer)),
                                   src_addr, dst_addr), (src_addr, src_port))
                conexao.send_callback = asyncio.get_event_loop().call_soon(send_next, fd, conexao)
    else:
        print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
            (src_addr, src_port, dst_addr, dst_port))

if __name__ == '__main__':
    fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
    loop = asyncio.get_event_loop()
    loop.add_reader(fd, raw_recv, fd)
    loop.run_forever()






