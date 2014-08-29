from utils import ENEMY_NAMES_TABLE, utilrandom as random

enemynames = [line.strip() for line in open(ENEMY_NAMES_TABLE).readlines()]
generator = {}
lookback = None
for line in open('tables/generator.txt'):
    key, values = tuple(line.strip().split())
    generator[key] = values
    if not lookback:
        lookback = len(key)


def generate_name(size=None):
    if not size:
        size = random.randint(1, 5) + random.randint(1, 5)
        if size < 4:
            size += random.randint(0, 5)
    while True:
        starts = [s for s in generator if s[0].isupper()]
        name = random.choice(starts)
        name = name[:size]
        while len(name) < size:
            key = name[-lookback:]
            if key not in generator or random.randint(1, 15) == 15:
                if len(name) <= size - lookback:
                    name += random.choice(starts)
                    continue
                else:
                    name = random.choice(starts)
                    continue

            c = random.choice(generator[key])
            name = name + c

        for ename in enemynames:
            if name == ename:
                name = ""
                break

        if name:
            for ename in enemynames:
                if len(name) > (lookback+1):
                    length = min(len(name), len(ename))
                    if name[:length] == ename[:length]:

                        name = ""
                        break

        if len(name) >= size:
            return name
