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

def read_varint(byte, i):
    result = 0
    for j in range(6):
        if j >= 5:#i在0~4共5个索引内，一共能读出5*7=35个bits，刚好大于32，如果再多则varint出错，抛出异常
            raise IOError("Packet is too long!")
        byte_in = byte[i]
        i += 1
        result |= (byte_in & 0x7F) << (j * 7)
        if (byte_in & 0x80) != 0x80:
            return result, i


def read_str(byte, i):
    (length, i) = read_varint(byte, i)
    ip = byte[i:(i + length)].decode('utf-8')
    i += length
    return ip, i

def read_byte(byte, i):
    new_i = i + 1
    return byte[i], new_i


def read_ushort(byte, i):
    new_i = i + 2
    return struct.unpack(">H", byte[i:new_i])[0], new_i


def read_long(byte, i):
    new_i = i + 8
    return struct.unpack(">q", byte[i:new_i]), new_i


def write_varint(byte, value):
    while True:
        part = value & 0x7F
        value >>= 7
        if value != 0:
            part |= 0x80
        byte.append(part)
        if value == 0:
            break


def write_byte(byte: bytearray, value):
    byte.append(value & 0xff)

def write_ushort(byte: bytearray, value):
    byte += struct.pack(">H", value)

def write_long(byte: bytearray, value):
    byte += struct.pack(">q", value)

def write_utf(byte, value):
    write_varint(byte, len(value))
    byte.extend(value.encode('utf-8'))

def write_response(client_socket, response):
    response_array = bytearray()
    write_byte(response_array, 0x00)
    write_utf(response_array, response)
    length = bytearray()
    write_varint(length, len(response_array))
    client_socket.sendall(bytes(length) + bytes(response_array))