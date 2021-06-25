import pathlib

class SpriteReplacement:
    def __init__(self, file, name, gender, riding=None, fallback_portrait_id=0xE, portrait_filename=None, uniqueids=None,
                 tags=None, opera=None, chains=None, hair=None, esper_fly=None):
        self.file = pathlib.Path(file.strip())
        self.name = name.strip()
        self.gender = gender.strip().lower()
        self.size = 0x16A0 if riding is not None and riding.lower() == "true" else 0x1560
        self.uniqueids = [s.strip() for s in uniqueids.split('|')] if uniqueids else []
        self.tags = [s.strip() for s in tags.split('|')] if tags else []
        if self.gender == "female":
            self.tags.append("girls")
        if self.gender == "male":
            self.tags.append("boys")
        self.weight = 1.0

        if fallback_portrait_id == '':
            fallback_portrait_id = 0xE
        self.fallback_portrait_id = int(fallback_portrait_id)
        self.portrait_filename = portrait_filename.strip()
        if self.portrait_filename:
            self.portrait_palette_filename = pathlib.Path(portrait_filename.strip()).with_suffix('.pal')
        else:
            self.portrait_palette_filename = None

        self.opera_filename = pathlib.Path(opera or self.file.stem + '-opera.bin')
        self.chains_filename = pathlib.Path(chains or self.file.stem + '-chains.bin')
        self.hair_filename = pathlib.Path(hair or self.file.stem + '-hair.bin')
        self.esper_fly_filename = pathlib.Path(esper_fly or self.file.stem + '-fly.bin')

    def has_custom_portrait(self):
        return self.portrait_filename is not None and self.portrait_palette_filename is not None

    def is_on(self, checklist):
        for g in self.uniqueids:
            if g in checklist:
                return True
        return False
