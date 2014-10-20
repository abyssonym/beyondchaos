SEED=42069
rm program.$SEED.rom program.$SEED.rom.bak
python randomizer.py program.rom .$1.$SEED
mv program.$SEED.rom program.$SEED.rom.bak
python randomizer.py program.rom .$1.$SEED
mv program.$SEED.rom program.$SEED.rom.bak2
python randomizer.py program.rom .$1.$SEED
diff program.$SEED.rom program.$SEED.rom.bak
diff program.$SEED.rom program.$SEED.rom.bak2
diff program.$SEED.rom.bak program.$SEED.rom.bak2
