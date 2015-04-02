from utils import read_multi
from sys import argv


def decompress(bytestring, simple=False, complicated=False, debug=False):
    result = ""
    buff = [chr(0)] * 2048
    buffaddr = 0x7DE
    while bytestring:
        flags, bytestring = ord(bytestring[0]), bytestring[1:]
        for i in xrange(8):
            if not bytestring:
                break

            if flags & (1 << i):
                byte, bytestring = bytestring[0], bytestring[1:]
                result += byte
                buff[buffaddr] = byte
                buffaddr += 1
                if buffaddr == 0x800:
                    buffaddr = 0
                if debug:
                    print "%x" % ord(byte),
            else:
                low, high, bytestring = (
                    ord(bytestring[0]), ord(bytestring[1]), bytestring[2:])
                seekaddr = low | ((high & 0x07) << 8)
                length = ((high & 0xF8) >> 3) + 3
                if simple:
                    copied = "".join([buff[seekaddr]] * length)
                elif complicated:
                    cycle = buffaddr - seekaddr
                    if cycle < 0:
                        cycle += 0x800
                    subbuff = "".join((buff+buff)[seekaddr:seekaddr+cycle])
                    while len(subbuff) < length:
                        subbuff = subbuff + subbuff
                    copied = "".join(subbuff[:length])
                else:
                    copied = "".join((buff+buff)[seekaddr:seekaddr+length])
                assert len(copied) == length
                result += copied
                if debug:
                    print "%x" % seekaddr, length,
                while copied:
                    byte, copied = copied[0], copied[1:]
                    buff[buffaddr] = byte
                    buffaddr += 1
                    if buffaddr == 0x800:
                        buffaddr = 0
                    if debug:
                        print "%x" % ord(byte),
            if debug:
                print
                import pdb; pdb.set_trace()
    return result


def recompress(bytestring):
    bytestring = "".join([chr(c) if type(c) is int else c for c in bytestring])
    result = ""
    buff = [chr(0)] * 2048
    buffaddr = 0x7DE
    while bytestring:
        control = 0x00
        subresult = ""
        for i in xrange(8):
            searchbuff = "".join(buff + buff)
            for j in xrange(35):
                if bytestring[:j] not in searchbuff:
                    break
            else:
                j = 0
            j = j - 1
            if j >= 3:
                substr = bytestring[:j]
                bytestring = bytestring[j:]
                index = searchbuff.find(substr)
                if index < 0:
                    index += 0x800

                try:
                    assert 0 <= index < 0x800
                    assert (j-3) & 0xFFE0 == 0
                except:
                    import pdb; pdb.set_trace()
                value = index << 5
                value = value | (j - 3)
                while substr:
                    c = substr[0]
                    substr = substr[1:]
                    buff[buffaddr] = c
                    buffaddr = (buffaddr + 1) % 0x800
                byte1 = index & 0xFF
                byte2 = (index >> 8) | ((j-3) << 3)
                assert byte1 | ((byte2 & 0x07) << 8) == index
                assert ((byte2 & 0xF8) >> 3) + 3 == j
                subresult += chr(byte1) + chr(byte2)
            else:
                control |= (1 << i)
                if bytestring:
                    c, bytestring = bytestring[0], bytestring[1:]
                else:
                    c = chr(0)
                subresult += c
                buff[buffaddr] = c
                buffaddr = (buffaddr + 1) % 0x800
        result += chr(control) + subresult
    return result


def decompress_at_location(filename, address):
    f = open(filename, 'r+b')
    f.seek(address)
    size = read_multi(f, length=2)
    bytestring = f.read(size)
    decompressed = decompress(bytestring, complicated=True)
    return decompressed

if __name__ == "__main__":
    d2 = decompress_at_location(argv[1], 0x2686C)
    initial_length = len(d2)
    initial_decompress = str(d2)
    d3 = recompress(d2)
    dx = decompress
    rx = recompress
    print len(d2), len(d3)
    for i in xrange(10):
        print d2 == initial_decompress,
        d2 = dx(rx(d2))
        print d2 == initial_decompress,
        print len(d2),
        print ["%x" % ord(i) for i in d2[initial_length:]]
        if d2 != initial_decompress:
            for a, b in zip(initial_decompress, d2):
                print "%x" % ord(b),
                if b != a:
                    print
                    print "%x %x" % (ord(a), ord(b))
                    import pdb; pdb.set_trace()
    import pdb; pdb.set_trace()
