from itemrandomizer import get_ranked_items
from monsterrandomizer import get_ranked_monsters
from skillrandomizer import get_ranked_spells
from utils import utilrandom as random
        
def manage_bingo(seed):
    target_score = 200.0
    print("WELCOME TO BEYOND CHAOS BINGO MODE")
    print("Include what type of squares? (blank for all)")
    print("    a   Abilities\n"
          "    i   Items\n"
          "    m   Monsters\n"
          "    s   Spells")
    bingoflags = input("> ").strip()
    if not bingoflags:
        bingoflags = "aims"
    bingoflags = [c for c in "aims" if c in bingoflags]

    print("What size grid? (default: 5)")
    size = input("> ").strip()
    if not size:
        size = 5
    else:
        size = int(size)
    target_score = float(target_score) * (size**2)

    print("What difficulty level? Easy, Normal, or Hard? (e/n/h)")
    difficulty = input("> ").strip()
    if not difficulty:
        difficulty = "n"
    else:
        difficulty = difficulty[0].lower()
        if difficulty not in "enh":
            difficulty = "n"

    print("Generate how many cards? (default: 1)")
    numcards = input("> ").strip()
    if not numcards:
        numcards = 1
    else:
        numcards = int(numcards)
    print("Generating Bingo cards, please wait.")

    skills = get_ranked_spells()
    spells = [s for s in skills if s.spellid <= 0x35]
    abilities = [s for s in skills if 0x54 <= s.spellid <= 0xED]
    monsters = get_ranked_monsters()
    items = get_ranked_items()
    monsters = [m for m in monsters if m.display_location and
                "missing" not in m.display_location.lower() and
                "unknown" not in m.display_location.lower() and
                m.display_name.strip('_')]
    monsterskills = set([])
    for m in monsters:
        ids = set(m.get_skillset(ids_only=True))
        monsterskills |= ids
    abilities = [s for s in abilities if s.spellid in monsterskills]
    if difficulty == 'e':
        left, right = lambda x: 0, lambda x: len(x)//2
    elif difficulty == 'h':
        left, right = lambda x: len(x)//2, len
    else:
        left, right = lambda x: 0, len

    abilities = abilities[left(abilities):right(abilities)]
    items = items[left(items):right(items)]
    monsters = monsters[left(monsters):right(monsters)]
    spells = spells[left(spells):right(spells)]

    difficulty = {'e': "Easy",
                  'n': "Normal",
                  'h': "Hard"}[difficulty]
    flagnames = {'a': "Ability",
                 'i': "Item",
                 'm': "Enemy",
                 's': "Spell"}

    def generate_card(grid):
        midborder = "+" + "+".join(["-"*12]*len(grid)) + "+"
        s = midborder + "\n"
        for row in grid:
            flags = ["{0:^12}".format(c.bingoflag.upper()) for c in row]
            names = ["{0:^12}".format(c.bingoname) for c in row]
            scores = ["{0:^12}".format("%s Points" % c.bingoscore)
                      for c in row]
            flags = "|".join(flags)
            names = "|".join(names)
            scores = "|".join(scores)
            rowstr = "|" + "|\n|".join([flags, names, scores]) + "|"
            s += rowstr + "\n"
            s += midborder + "\n"
        return s.strip()

    for i in range(numcards):
        flaglists = {'a': list(abilities),
                     'i': list(items),
                     'm': list(monsters),
                     's': list(spells)}
        scorelists = {x:dict({}) for x in "aims"}
        random.seed(seed + (i**2))
        grid, flaggrid, displaygrid = [], [], []
        filename = "bingo.%s.%s.txt" % (seed, i)
        s = "Beyond Chaos Bingo Card %s-%s\n" % (i, difficulty)
        s += "Seed: %s\n" % seed
        for y in range(size):
            for g in [grid, flaggrid, displaygrid]:
                g.append([])
            for x in range(size):
                flagoptions = set(bingoflags)
                if y > 0 and flaggrid[y-1][x] in flagoptions:
                    flagoptions.remove(flaggrid[y-1][x])
                if x > 0 and flaggrid[y][x-1] in flagoptions:
                    flagoptions.remove(flaggrid[y][x-1])
                if not flagoptions:
                    flagoptions = set(bingoflags)
                chosenflag = random.choice(sorted(flagoptions))
                flaggrid[y].append(chosenflag)
                chosen = random.choice(flaglists[chosenflag])
                flaglists[chosenflag].remove(chosen)
                scorelists[chosenflag][chosen] = (x, y)
                grid[y].append(chosen)
        for flag in bingoflags:
            scoredict = scorelists[flag]
            chosens = list(scoredict.keys())
            scoresum = sum([c.rank() for c in chosens])
            multiplier = target_score / scoresum
            for c in chosens:
                c.bingoscore = int(round(c.rank() * multiplier, -2))
                c.bingoflag = flagnames[flag]
                c.bingoname = (c.display_name if hasattr(c, "display_name")
                               else c.name)

        assert len(grid) == size
        assert len(grid[0]) == size
        s2 = generate_card(grid)
        s += "\n" + s2
        f = open(filename, "w+")
        f.write(s)
        f.close()
