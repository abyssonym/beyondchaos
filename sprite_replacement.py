class SpriteReplacement:
    def __init__(self, file, name, gender, riding=None, fallback_portrait_id=0xE, portrait_filename=None, uniqueids=None, groups=None):
        self.file = file.strip()
        self.name = name.strip()
        self.gender = gender.strip().lower()
        self.size = 0x16A0 if riding is not None and riding.lower() == "true" else 0x1560
        self.uniqueids = [s.strip() for s in uniqueids.split('|')] if uniqueids else []
        self.groups = [s.strip() for s in groups.split('|')] if groups else []
        if self.gender == "female":
            self.groups.append("girls")
        if self.gender == "male":
            self.groups.append("boys")
        self.weight = 1.0

        if fallback_portrait_id == '':
            fallback_portrait_id = 0xE
        self.fallback_portrait_id = int(fallback_portrait_id)
        self.portrait_filename = portrait_filename
        if self.portrait_filename is not None:
            self.portrait_filename = self.portrait_filename.strip()
            if self.portrait_filename:
                self.portrait_palette_filename = portrait_filename.strip()
                if self.portrait_palette_filename and self.portrait_palette_filename:
                    if self.portrait_palette_filename[-4:] == ".bin":
                        self.portrait_palette_filename = self.portrait_palette_filename[:-4]
                    self.portrait_palette_filename = self.portrait_palette_filename + ".pal"
            else:
                self.portrait_filename = None

    def has_custom_portrait(self):
        return self.portrait_filename is not None and self.portrait_palette_filename is not None

    def is_on(self, checklist):
        for g in self.uniqueids:
            if g in checklist:
                return True
        return False