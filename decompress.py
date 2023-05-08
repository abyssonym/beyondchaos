#!/usr/bin/env python3

from sys import argv
from shutil import copyfile

from utils import read_multi

WINDOW_SIZE = 0x800
WINDOW_START = 0x7de # why start here?

MIN_MULTI_LENGTH = 3
MAX_MULTI_LENGTH = 34
MAX_COMPRESS_SIZE = 2 ** 16 - 1

def recompress(data):
    result = []
    data_index = 0

    group = []
    control_byte = 0
    control_bit = 1

    byte_positions = {} # lists of sorted positions each byte occurs at
    window_indices = {} # start indices of byte_positions within current window
    for index, byte in enumerate(data):
        if byte in byte_positions:
            byte_positions[byte].append(index)
        else:
            byte_positions[byte] = [index]
            window_indices[byte] = 0

    while data_index < len(data):
        longest_length = 0
        longest_start = 0

        start_byte = data[data_index]
        for x in range(window_indices[start_byte], len(byte_positions[start_byte])):
            position = byte_positions[start_byte][x]

            if position >= data_index:
                # window has not reached position yet, skip the rest of the positions
                break
            if position < data_index - WINDOW_SIZE:
                # position is no longer within the window, increment window index for this byte and go to next position
                window_indices[start_byte] += 1
                continue

            try:
                length = 1
                while length < MAX_MULTI_LENGTH and data[data_index + length] == data[position + length]:
                    length += 1
            except IndexError:
                pass

            if length > longest_length:
                longest_length = length
                longest_start = position
                if length == MAX_MULTI_LENGTH:
                    break

        if longest_length >= MIN_MULTI_LENGTH:
            length_start = ((longest_start + WINDOW_START) % WINDOW_SIZE) | ((longest_length - MIN_MULTI_LENGTH) << 11)
            group.extend(list(length_start.to_bytes(2, "little")))
            data_index += longest_length
        else:
            control_byte = control_byte | control_bit
            group.append(data[data_index])
            data_index += 1

        control_bit <<= 1
        if control_bit > 0xff:
            result.append(control_byte)
            result.extend(group)
            control_byte = 0
            control_bit = 1
            group = []

    result.append(control_byte)
    result.extend(group)

    size = len(result) + 2
    if size > MAX_COMPRESS_SIZE:
        print(f"error: compress: data too large (compressed size {size} > {MAX_COMPRESS_SIZE})")
        size = MAX_COMPRESS_SIZE
    return list(size.to_bytes(2, "little")) + result

def decompress(data):
    window = [0] * WINDOW_SIZE
    window_index = WINDOW_START

    result = []
    data_index = 2 # first two bytes should be len(data)
    assert int.from_bytes(data[ : data_index], byteorder = "little") == len(data)
    while data_index < len(data):
        control_byte = data[data_index]
        data_index += 1

        control_bit = 1
        while control_bit <= 0xff and data_index < len(data):
            if control_bit & control_byte:
                # copy single value from data
                value = data[data_index]
                data_index += 1
                result.append(value)
                window[window_index] = value
                window_index = (window_index + 1) % WINDOW_SIZE
            else:
                # copy multiple values from window
                length_start = int.from_bytes(data[data_index : data_index + 2], byteorder = "little")
                data_index += 2

                length = (length_start >> 11) + MIN_MULTI_LENGTH
                start = length_start % WINDOW_SIZE
                for position in range(start, start + length):
                    value = window[position % WINDOW_SIZE]
                    result.append(value)
                    window[window_index] = value
                    window_index = (window_index + 1) % WINDOW_SIZE
            control_bit <<= 1
    return result

def decompress_at_location(filename, address):
    f = open(filename, 'r+b')
    f.seek(address)
    size = read_multi(f, length=2)
    #print "Size is %s" % size
    f.seek(address)
    bytestring = f.read(size)
    decompressed = bytearray(decompress(bytestring))
    return decompressed


class Decompressor():
    def __init__(self, address, fakeaddress=None, maxaddress=None):
        self.address = address
        self.fakeaddress = fakeaddress
        self.maxaddress = maxaddress
        self.data = None

    def read_data(self, filename):
        self.data = decompress_at_location(filename, self.address)
        #assert decompress(recompress(self.data)) == list(self.data)

    def writeover(self, address, to_write):
        to_write = bytes([c if isinstance(c, int) else ord(c) for c in to_write])
        if self.fakeaddress:
            address = address - self.fakeaddress
        self.data = (self.data[:address] + to_write +
                     self.data[address+len(to_write):])

    def get_bytestring(self, address, length):
        if self.fakeaddress:
            address = address - self.fakeaddress
        return self.data[address:address+length]

    def compress_and_write(self, fout):
        compressed = recompress(self.data)
        #print "Recompressed is %s" % len(compressed)
        if self.maxaddress:
            length = self.maxaddress - self.address
            fout.seek(self.address)
            fout.write(bytes([0xFF]*length))
        fout.seek(self.address)
        fout.write(bytes(compressed))
        if self.maxaddress and fout.tell() >= self.maxaddress:
            raise Exception("Recompressed data out of bounds.")

if __name__ == "__main__":
    sourcefile = argv[1]
    outfile = argv[2]
    copyfile(sourcefile, outfile)
    d = Decompressor(0x2686C, fakeaddress=0x7E5000, maxaddress=0x28A70)
    d.read_data(sourcefile)
    print(["%x" % i for i in d.get_bytestring(0x7E7C43, 0x20)])
    d.writeover(0x7E50F7, [0x0] * 57)
    d.writeover(0x7E501A, [0xEA] * 3)
    d.compress_and_write(outfile)
