import pathlib

class SpriteReplacement:
    def __init__(self, file, name, gender, riding=None, fallback_portrait_id=0xE, portrait_filename=None, uniqueids=None,
                 tags=None, *, path=pathlib.Path('custom', 'sprites')):
        self.file = pathlib.Path(path, file.strip())
        self.name = name.strip()
        self.gender = gender.strip().lower()
        self.size = 0x16A0 if riding is not None and riding.lower() == 'true' else 0x1560
        self.uniqueids = [s.strip() for s in uniqueids.split('|')] if uniqueids else []
        self.tags = [s.strip() for s in tags.split('|')] if tags else []
        if self.gender == 'female':
            self.tags.append('girls')
        if self.gender == 'male':
            self.tags.append('boys')
        self.weight = 1.0
        self.path = path

        if fallback_portrait_id == '':
            fallback_portrait_id = 0xE
        self.fallback_portrait_id = int(fallback_portrait_id)
        if portrait_filename:
            self.portrait_filename = pathlib.Path(path, portrait_filename.strip()) 
            self.portrait_palette_filename = self.portrait_filename.with_suffix('.pal')
        else:
            self.portrait_filename = None
            self.portrait_palette_filename = None

        self.opera_filename = pathlib.Path(path, self.file.stem + '-opera.bin')
        self.chains_filename = pathlib.Path(path, self.file.stem + '-chains.bin')
        self.hair_filename = pathlib.Path(path, self.file.stem + '-hair.bin')
        self.esper_fly_filename = pathlib.Path(path, self.file.stem + '-fly.bin')

    def has_custom_portrait(self):
        return self.portrait_filename is not None and self.portrait_palette_filename is not None

    def is_on(self, checklist):
        for g in self.uniqueids:
            if g in checklist:
                return True
        return False
