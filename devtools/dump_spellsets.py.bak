#!/usr/bin/env python

"""Usage: dump_spellsets.py <ROM file>

Dump the spellsets that skillrandomizer uses for generating new PC commands
(R-Nuke, 3xBeast, W-Sword, etc.)
"""
from __future__ import print_function

import os
import sys
import textwrap
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from skillrandomizer import SpellBlock, get_spellsets, spelldict

sourcefile = sys.argv[1]

print("Loading skills from '{0}'".format(sourcefile))

all_spells = [SpellBlock(i, sourcefile) for i in xrange(0xFF)]

for s in all_spells:
    spelldict[s.spellid] = s

valid_spells = [s for s in all_spells if s.valid]
spellsets = get_spellsets(valid_spells)

for name in sorted(spellsets.keys()):
    desc, spells = spellsets[name]
    print("\n\n{0}\n==========".format(name))
    print("Set members are described as '{0}'".format(desc))
    print(textwrap.fill("".join("{0:13}".format(s.name) for s in spells), 76))
