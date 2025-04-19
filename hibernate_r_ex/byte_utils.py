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
    bytes_ = 0
    while True:
        byte_in = byte[i]
        i += 1
        result |= (byte_in & 0x7F) << (bytes_ * 7)
        if bytes_ > 32:
            raise IOError("Packet is too long!")
        if (byte_in & 0x80) != 0x80:
            return result, i


def read_utf(byte, i):
    (length, i) = read_varint(byte, i)
    ip = byte[i:(i + length)].decode('utf-8')
    i += length
    return ip, i


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


def write_utf(byte, value):
    write_varint(byte, len(value))
    byte.extend(value.encode('utf-8'))

def write_response(client_socket, response):
    response_array = bytearray()
    write_varint(response_array, 0)
    write_utf(response_array, response)
    length = bytearray()
    write_varint(length, len(response_array))
    client_socket.sendall(bytes(length)+bytes(response_array))