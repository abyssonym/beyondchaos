from utils import utilrandom as random
from itemrandomizer import get_ranked_items

items = None


class ShopBlock:
    def __init__(self, pointer):
        #self.pointer = hex2int(pointer)
        self.pointer = pointer

    def read_data(self, filename):
        global items

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.misc = ord(f.read(1))
        self.items = map(ord, f.read(8))
        f.close()

        if items is None:
            items = get_ranked_items(filename)

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.write(chr(self.misc))
        f.write("".join(map(chr, self.items)))
        f.close()

    @property
    def discount(self):
        return self.misc & 0xF0

    @property
    def shoptype(self):
        return self.misc & 0x0F

    def mutate_misc(self):
        self.misc &= 0x0F
        value = random.randint(1, 10)
        if value <= 5:
            self.misc |= 0x20
        elif value <= 8:
            self.misc |= 0x10
        elif value <= 9:
            self.misc |= 0x30

    def mutate_items(self, filename):
        if self.shoptype == 1:
            valid_items = [c for c in items if c.is_weapon or c.is_tool]
        elif self.shoptype == 2:
            valid_items = [c for c in items if c.is_armor]
        elif self.shoptype == 3:
            valid_items = [c for c in items if not (c.is_weapon or c.is_armor or c.is_relic)]
        elif self.shoptype == 4:
            valid_items = [c for c in items if c.is_relic]
        elif self.shoptype == 5:
            valid_items = list(items)

        old_items = [i for i in self.items if i != 0xFF]
        if not old_items:
            return
        old_items = [[j for j in items if j.itemid == i][0] for i in old_items]

        average_value = sum([i.rank() for i in old_items]) / len(old_items)
        average_item = len([i for i in valid_items if i.rank() <= average_value])
        average_item += -1
        average_item = valid_items[average_item]

        while random.randint(1, 3) == 3 and len(old_items) < 8:
            old_items.append(average_item)
        new_items = []
        for item in old_items:
            if random.randint(1, 10) == 10:
                candidates = items
            else:
                candidates = valid_items

            try:
                index = candidates.index(item)
            except ValueError:
                continue

            while random.randint(1, 3) < 3:
                index += random.randint(-2, 2)
                index = max(0, min(index, len(candidates)-1))
            new_items.append(candidates[index])

        if not new_items:
            return

        for i in new_items:
            if i.price < 3:
                price = i.rank()
                modifier = price / 2
                price += random.randint(0, modifier)
                while random.randint(1, 4) < 4:
                    price += random.randint(0, modifier)
                price = min(price, 0xFEFE)
                i.price = price

                zerocount = 0
                while i.price > 100:
                    i.price = i.price / 10
                    zerocount += 1

                while zerocount > 0:
                    i.price = i.price * 10
                    zerocount += -1

                i.write_stats(filename)

        self.items = [i.itemid for i in new_items]
        self.items = sorted(set(self.items))
        while len(self.items) < 8:
            self.items.append(0xFF)

        assert len(self.items) == 8
