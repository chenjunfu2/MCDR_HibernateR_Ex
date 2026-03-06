import struct
import socket
import time
import uuid


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


def format_hex(data, sep=' ', prefix='', case='upper'):
    """
    格式化字节数组为十六进制字符串
    参数：
        data: bytes/bytearray 原始二进制数据
        sep: 分隔符 (默认空格)
        prefix: 前缀 (如 '0x', '$' 等)
        case: 大小写控制 ('upper'/'lower')
    """
    case = case.lower()
    fmt = f"{{:{prefix}02{'X' if case == 'upper' else 'x'}}}"
    return sep.join(fmt.format(b) for b in data)


class BytesReaderError(Exception):
    def __init__(self, message):
        self.message = message
    
    def __str__(self):
        return self.message


class BytesReader:
    def __init__(self, data: bytes, i: int = 0):
        self.data = data
        self.i = i  # 当前读取位置索引
    
    def len(self):
        return len(self.data)
    
    def getdata(self):
        return self.data
    
    def read_varint(self):
        result = 0
        
        for j in range(6):
            if j >= 5:  # i在0~4共5个索引内，一共能读出5*7=35个bits，刚好大于32，如果再多则varint出错，抛出异常
                raise BytesReaderError("Insufficient data for varint")
            
            byte_in = self.data[self.i]
            self.i += 1
            result |= (byte_in & 0x7F) << (j * 7)
            if (byte_in & 0x80) != 0x80:
                break
        
        return result
    
    def read_str(self):
        length = self.read_varint()
        
        if self.i + length > len(self.data):
            raise BytesReaderError("Insufficient data for string")
        
        old_i = self.i
        self.i += length
        return self.data[old_i:self.i].decode('utf-8')
    
    def read_bytes(self, size):
        if self.i + size > len(self.data):
            raise BytesReaderError(f"Insufficient data for [{size}]bytes")
        
        old_i = self.i
        self.i += size
        return self.data[old_i:self.i]
    
    def read_byte(self):
        if self.i + 1 > len(self.data):
            raise BytesReaderError("Insufficient data for byte")
        
        old_i = self.i
        self.i += 1
        return self.data[old_i]
    
    def read_int(self):
        if self.i + 4 > len(self.data):
            raise BytesReaderError("Insufficient data for int")
        
        old_i = self.i
        self.i += 4
        return struct.unpack(">i", self.data[old_i:self.i])[0]
    
    def read_ushort(self):
        if self.i + 2 > len(self.data):
            raise BytesReaderError("Insufficient data for ushort")
        
        old_i = self.i
        self.i += 2
        return struct.unpack(">H", self.data[old_i:self.i])[0]
    
    def read_long(self):
        if self.i + 8 > len(self.data):
            raise BytesReaderError("Insufficient data for long")
        
        old_i = self.i
        self.i += 8
        return struct.unpack(">q", self.data[old_i:self.i])[0]
    
    def read_uuid(self):
        # 编码为无符号的 128 位整数uuid，16bytes
        if self.i + 16 > len(self.data):
            raise BytesReaderError("Insufficient data for uuid")
        
        old_i = self.i
        self.i += 16
        return uuid.UUID(bytes=self.data[old_i:self.i])
    
    def unread(self, length):
        if length > self.i:
            raise BytesReaderError("Unread length out of range")
        self.i -= length
        return self.i


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


def write_utf(byte: bytearray, value):
    write_varint(byte, len(value))
    byte.extend(value.encode('utf-8'))


def write_str_response(client_socket, packet_id, response):
    # 写入包头：packet_id
    response_array = bytearray()
    write_byte(response_array, packet_id)
    # 写入字符串
    write_utf(response_array, response)
    # 写入长度
    length = bytearray()
    write_varint(length, len(response_array))
    # 发送数据
    client_socket.sendall(bytes(length) + bytes(response_array))