from utils import SHOP_TABLE, utilrandom as random
from itemrandomizer import get_ranked_items, get_item

# Despite documentation, these are the only pricings available.
# 0 x1 price
# 1 x2 price
# 2 x1.5 price female discount
# 3 x1 price figaro discount
price_multipliers = {0: 1,
                     1: 2,
                     2: 1.5,
                     3: 1}


class ShopBlock:
    def __init__(self, pointer, name):
        #self.pointer = hex2int(pointer)
        self.pointer = pointer
        self.name = name
        self.shopid = None
        self.items = None
        self.misc = None

    def set_id(self, shopid):
        self.shopid = shopid

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.misc = ord(f.read(1))
        self.items = bytes(f.read(8))
        f.close()

    def write_data(self, fout):
        fout.seek(self.pointer)
        fout.write(bytes([self.misc]))
        fout.write(bytes(self.items))

    def __repr__(self):
        multiplier = price_multipliers[self.discount]
        s = "%s %s\n" % (self.name, self.shoptype_pretty)
        s = s.upper()
        if self.discount == 2:
            s += "Discounts for female characters.\n"
        items = [get_item(i) for i in self.items]
        items = [i for i in items if i is not None]
        for i in items:
            s2 = "{0:13} {1:>5}\n".format(i.name, int(i.price * multiplier))
            s += s2
        return s.strip()

    @property
    def discount(self):
        return (self.misc & 0xF0) >> 4

    @property
    def shoptype(self):
        return self.misc & 0x0F

    @property
    def shoptype_pretty(self):
        shoptypes = {1: "weapons", 2: "armor", 3: "items",
                     4: "relics", 5: "misc"}
        return shoptypes[self.shoptype]

    def mutate_misc(self):
        self.misc &= 0x0F
        value = random.randint(1, 20)
        if value <= 3:
            self.misc |= 0x20
        elif value <= 9:
            self.misc |= 0x10

        for i in self.items:
            i = get_item(i)
            if i is None:
                continue
            if i.price * price_multipliers[self.discount] > 65535:
                self.misc &= 0x0F
                break

    def mutate_items(self, fout, crazy_shops=False):
        items = get_ranked_items()
        if crazy_shops:
            weapons_tools = [i for i in items if i.is_weapon or i.is_tool]
            armors = [i for i in items if i.is_armor]
            relics = [i for i in items if i.is_relic]
            consumables = [i for i in items if i.is_consumable]

            types = [weapons_tools, armors, relics, consumables]

            valid_items = items
        elif self.shoptype == 1:
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
        old_items = [get_item(i) for i in old_items]
        old_items = [i for i in old_items if i]

        if not old_items:
            average_value = 0
        else:
            average_value = sum([i.rank() for i in old_items]) / len(old_items)
        average_item = len([i for i in valid_items if i.rank() <= average_value])
        average_item += -1
        average_item = valid_items[average_item]

        while (crazy_shops or random.randint(1, 3) == 3) and len(old_items) < 8:
            old_items.append(average_item)
        new_items = []

        for item in old_items:
            if crazy_shops:
                item_type = random.choice(types)
                new_items.append(random.choice(item_type))
            else:
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
                modifier = price // 2
                price += random.randint(0, modifier)
                while random.randint(1, 4) < 4:
                    price += random.randint(0, modifier)
                price = min(price, 0xFEFE)
                i.price = price

                zerocount = 0
                while i.price > 100:
                    i.price = i.price // 10
                    zerocount += 1

                while zerocount > 0:
                    i.price = i.price * 10
                    zerocount += -1

                i.write_stats(fout)

        self.items = [i.itemid for i in new_items]
        self.items = sorted(set(self.items))
        while len(self.items) < 8:
            self.items.append(0xFF)

        assert len(self.items) == 8

    def rank(self):
        items = [get_item(i) for i in self.items]
        items = [i for i in items if i]
        priciest = max(items, key=lambda i: i.price)
        return priciest.price


def buy_owned_breakable_tools(fout):
    fout.seek(0x3b7f4)
    fout.write(b'\x27')


all_shops = None


def get_shops(sourcefile):
    global all_shops
    if all_shops:
        return all_shops

    shop_names = [line.strip() for line in open(SHOP_TABLE).readlines()]
    all_shops = []
    for i, name in zip(range(0x80), shop_names):
        if "unused" in name.lower():
            continue
        pointer = 0x47AC0 + (9*i)
        s = ShopBlock(pointer, name)
        s.set_id(i)
        s.read_data(sourcefile)
        all_shops.append(s)

    return get_shops(sourcefile)
