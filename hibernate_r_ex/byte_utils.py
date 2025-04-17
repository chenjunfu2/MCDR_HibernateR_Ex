import struct
import socket
import time


def read_exactly(sock, n, timeout=5):
    """读取指定长度的数据，超时或连接关闭时抛出异常"""
    data = bytearray()
    end_time = time.time() + timeout
    while len(data) < n:
        remaining = end_time - time.time()
        if remaining <= 0:
            raise socket.timeout(f'Timeout after {timeout} seconds')
        sock.settimeout(remaining)
        try:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("连接已关闭")
            data.extend(chunk)
        except socket.timeout:
            raise
        except:
            raise
    return bytes(data)

def read_varint(sock):
    result = 0
    for i in range(5):
        byte_in = read_exactly(sock,1,timeout=2)[0]
        result |= (byte_in & 0x7F) << (i * 7)
        if (byte_in & 0x80) != 0x80:
            break
    return result
'''VarInt用于编码int类型，占1~5个字节，每个字节用低七位来编码数字。
最高一位如果为1，表示还有下一字节。最高位为0，表示没有下一字节了。
表示低有效位的字节排在前面，表示高有效位的字节排在后面。
符号位无需单独处理，不把符号位看成符号位就行'''


def read_utf(sock):
    length = read_varint(sock)
    byte = read_exactly(sock,length,timeout=5)
    ip = byte.decode('utf-8')
    return ip


def read_ushort(sock):
    byte = read_exactly(sock,2,timeout=5)
    return struct.unpack(">H", byte)[0]


def read_long(sock):
    byte = read_exactly(sock,8,timeout=5)
    return struct.unpack(">q", byte)[0]


def write_varint(byte, value):
    while True:
        part = value & 0x7F
        value >>= 7
        if value != 0:
            part |= 0x80
        byte.append(part)
        if value == 0:
            break


def write_utf(byte, value):
    write_varint(byte, len(value))
    byte.extend(value.encode('utf-8'))

def write_response(client_socket, response):
    response_array = bytearray()
    write_varint(response_array, 0)
    write_utf(response_array, response)
    length = bytearray()
    write_varint(length, len(response_array))
    client_socket.sendall(bytes(length) + bytes(response_array))
