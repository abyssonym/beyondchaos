from utils import read_multi
from sys import argv


def decompress(bytestring, simple=False, complicated=True, debug=False):
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
                    if buffaddr == seekaddr:
                        raise Exception("buffaddr equals seekaddr")
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
    global buffaddr
    bytestring = "".join([chr(c) if type(c) is int else c for c in bytestring])
    result = ""
    buff = [chr(0)] * 2048
    buffaddr = 0x7DE

    def add_buff(c):
        global buffaddr
        buff[buffaddr] = c
        buffaddr += 1
        buffaddr = buffaddr % 0x800

    while bytestring:
        control = 0x00
        subresult = ""
        for i in xrange(8):
            searchbuff = "".join(buff + buff)
            for j in xrange(3, 35):
                searchstr = bytestring[:j]
                if searchstr not in searchbuff:
                    break
                location = searchbuff.find(searchstr)
                if location == buffaddr:
                    location = searchbuff[location+1:].find(searchstr)
                    if location < 0:
                        break
                    location = buffaddr + location + 1
                    if location % 0x800 == buffaddr:
                        break
            else:
                j = 0
            j = j - 1
            goodloop = None
            loopbuff = "".join(buff[:buffaddr])
            #if len(loopbuff) < 35:
            #    loopbuff = "".join(buff) + loopbuff
            for k in xrange(j+1, 35):
                searchstr = bytestring[:k]
                for h in xrange(1, len(searchstr)+1):
                    loopstr = searchstr[:h]
                    mult = (len(searchstr) / len(loopstr)) + 1
                    if searchstr == (loopstr * mult)[:len(searchstr)]:
                        if loopbuff.endswith(loopstr):
                            j = k
                            goodloop = loopstr
            if len(bytestring) <= (8 - i):
                j = 0
            if j >= 3:
                substr = bytestring[:j]
                bytestring = bytestring[j:]
                if not goodloop:
                    index = searchbuff.find(substr)
                    if index % 0x800 == buffaddr:
                        index = searchbuff[index+1:].find(substr)
                        index += buffaddr + 1
                        assert index >= 0
                        assert index % 0x800 != buffaddr
                else:
                    index = len(loopbuff) - len(goodloop)
                if index < 0:
                    index += 0x800
                index = index % 0x800

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
                    add_buff(c)
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
                add_buff(c)
        result += chr(control) + subresult
    return result


def decompress_at_location(filename, address):
    f = open(filename, 'r+b')
    f.seek(address)
    size = read_multi(f, length=2)
    print "Size is %s" % size
    bytestring = f.read(size)
    decompressed = decompress(bytestring, complicated=True)
    return decompressed

if __name__ == "__main__":
    f = open(argv[1], 'r+b')
    f.seek(0x2686C + 2)
    original_data = f.read(8692)
    f.close()
    d2 = decompress_at_location(argv[1], 0x2686C)
    initial_length = len(d2)
    initial_decompress = str(d2)
    d3 = recompress(d2)
    print "Recompressed is %s" % len(d3)
    '''
    if d3 != original_data:
        for i, (a, b) in enumerate(zip(d3, original_data)):
            print "%x" % ord(a),
            if a != b:
                print
                print "%s: " % i,
                print "%x %x" % (ord(a), ord(b))
                import pdb; pdb.set_trace()
    '''
    dx = decompress
    rx = recompress
    print len(d2), len(d3)
    for i in xrange(10):
        print d2 == initial_decompress,
        r2 = rx(d2)
        print len(r2),
        d2 = dx(r2)
        print d2 == initial_decompress,
        print len(d2)
        if d2[:len(initial_decompress)] != initial_decompress:
            for a, b in zip(initial_decompress, d2):
                print "%x" % ord(b),
                if b != a:
                    print
                    print "%x %x" % (ord(a), ord(b))
                    import pdb; pdb.set_trace()
    import pdb; pdb.set_trace()
