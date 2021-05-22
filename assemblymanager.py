#!/usr/bin/env python3
#
# This code manages a set of assembly language patches built from .asm files.
#
# The patches are written against version 10 of the "bass" assembler by byuu.
# Because bass is an external C++ program, we can't use it and remain portable.
# To solve that, we only require bass for building binary patch files, which
# are then committed and given to end users.  Only developers will need bass.

import os
import platform
import struct
import subprocess
import sys


TEMP_DIR = "build"
ASSEMBLER_DIR = os.path.join("assembly", "assemblers")
SOURCE_DIR = os.path.join("assembly", "source")
PATCH_DIR = os.path.join("assembly", "patches")

ASSEMBLER_BASS = "bass-v15"

PATCH_LIST_FILE = os.path.join(SOURCE_DIR, "_filelist.txt")
PATCH_EXTENSION = ".patch.bin"

PATCH_MAGIC = b"FF6PATCH"
DWORD_FORMAT = "<I"
PATCH_ENTRY_FORMAT = "<II"

# Architecture alias names
ARCH_ALIASES = {
    "i486" : "i386",
    "i586" : "i386",
    "i686" : "i386",
    "amd64" : "x86_64",
    "AMD64" : "x86_64",
    "arm64" : "aarch64",
    "ARM64" : "aarch64",
}
# Platform,architecture pairs that can run extra architectures
ARCH_COMPATIBILITY = {
    "win32,x86_64" : ["i386"], # i386 runs on Windows AMD64 via WOW64
    "win32,aarch64" : ["i386"], # i386 runs on Windows ARM64 via WOW64
}


# Thrown on assembler failure.
class AssemblerError(Exception):
    pass
# Thrown on patch format error.
class PatchFormatError(Exception):
    pass


# A loaded assembly patch.
class AssemblyPatch:
    def __init__(self):
        self.name = ""
        self.patches = []
        self.exports = {}

    def __str__(self):
        return str({"name" : self.name, "patches" : self.patches, "exports" : self.exports})

    def write(self, fout):
        for patch in self.patches:
            fout.seek(patch["offset"])
            fout.write(patch["data"])


# Code to simplify decoding logic.
class DecodeBuffer:
    def __init__(self, data, offset, size):
        self.data = data
        self.offset = offset
        self.size = size
        self.end = offset + size

    def unpack(self, decoder):
        self._check()
        try:
            if isinstance(decoder, struct.Struct):
                if decoder.size > self.end - self.offset:
                    self.data = None
                    raise PatchFormatError("Attempted to read past end of patch file")
                result = decoder.unpack(self.data[self.offset : self.offset + decoder.size])
                self.offset += decoder.size
            else:
                tempsize = struct.calcsize(decoder)
                if tempsize > self.end - self.offset:
                    self.data = None
                    raise PatchFormatError("Attempted to read past end of patch file")
                result = struct.unpack(decoder, self.data[self.offset : self.offset + tempsize])
                self.offset += tempsize
        except struct.error:
            self.data = None
            raise PatchFormatError("Patch file decode failure")
        return result

    def unpack_cstring(self):
        self._check()
        string_start = self.offset
        while True:
            if self.offset == self.end:
                self.data = None
                raise PatchFormatError("Attempted to read past end of patch file")
            if self.data[self.offset] == 0:
                try:
                    result = self.data[string_start : self.offset].decode(encoding="utf-8")
                except UnicodeError:
                    self.data = None
                    raise PatchFormatError("Non-UTF-8 string encountered")
                self.offset += 1
                return result
            else:
                self.offset += 1

    def unpack_raw(self, size):
        self._check()
        if size > self.end - self.offset:
            self.data = None
            raise PatchFormatError("Attempted to read past end of patch file")
        result = self.data[self.offset : self.offset + size]
        self.offset += size
        return result

    def at_end(self):
        self._check()
        return self.offset >= self.end

    def _check(self):
        if self.data is None:
            raise ValueError("Used DecodeBuffer object after an error")


# Decodes the export table from a patch file.
def decode_export_table(buffer):
    dword_decoder = struct.Struct(DWORD_FORMAT)
    entries = []

    while True:
        # End of table?
        if buffer.at_end():
            break

        export_name = buffer.unpack_cstring()
        export_value = buffer.unpack(dword_decoder)[0]
        entries += [[export_name, export_value]]

    result = {}
    for entry in entries:
        if entry[0] in result:
            raise PatchFormatError("Duplicate export name " + entry[0])
        result[entry[0]] = entry[1]

    return result


# Decodes a patch.
def decode_patch(buffer):
    patch_entry_decoder = struct.Struct(PATCH_ENTRY_FORMAT)

    # Check for magic value.
    if buffer.unpack_raw(len(PATCH_MAGIC)) != PATCH_MAGIC:
        raise PatchFormatError("No magic value in patch file")

    # Get the fixed data.
    patch_name = buffer.unpack_cstring()
    patch_count = buffer.unpack(DWORD_FORMAT)[0]

    # Read patch list.
    patches = []
    for _ in range(patch_count):
        patch_offset, patch_size = buffer.unpack(patch_entry_decoder)
        patch_data = buffer.unpack_raw(patch_size)
        patches += [{"offset" : patch_offset, "data" : patch_data}]

    # Read export table.
    exports = decode_export_table(buffer)

    # Build resulting object.
    patch = AssemblyPatch()
    patch.name = patch_name
    patch.patches = patches
    patch.exports = exports
    return patch


# Loads a patch from a whole file.
def load_patch(fin):
    data = None
    if isinstance(fin, str):
        with open(fin, "rb") as fin:
            data = fin.read()
    else:
        data = fin.read()
    return decode_patch(DecodeBuffer(data, 0, len(data)))


# Builds an executable path.
def build_exe_path(base, platform, arch, distro):
    suffix = ""
    if platform == "win32":
        suffix = ".exe"

    if distro is not None:
        distro = "-" + distro
    else:
        distro = ""

    return os.path.join(ASSEMBLER_DIR, base + "-" + platform + distro + "-" + arch + suffix)


# Get the path to an assembler executable.
def get_assembler_path(base):
    plat = sys.platform
    if plat == "":
        raise RuntimeError("Unknown platform")

    # Determine and canonicalize the system architecture name.
    arch = platform.machine()
    if arch == "":
        raise RuntimeError("Unknown system architecture")
    if arch in ARCH_ALIASES:
        arch = ARCH_ALIASES[arch]

    # Determine which other architectures' executables we can run.
    arch_compat = [arch]
    arch_compat_index = plat + "," + arch
    if arch_compat_index in ARCH_COMPATIBILITY:
        arch_compat += ARCH_COMPATIBILITY[arch_compat_index]

    # Try to find one that is available.
    for try_arch in arch_compat:
        exe = build_exe_path(base, plat, try_arch, None)
        if os.access(exe, os.X_OK):
            return exe

    raise RuntimeError("Could not find an assembler for this machine")


# Build a single 65816 patch.
def build_65816_patch(name, bass_path, new_rom_size):
    # The algorithm we do here is to build the assembly patches twice,
    # once with untouched bytes filled with 00 and once filled with FF.
    # This tells us which bytes the patch is overwriting.

    # Create temporary output directory if it doesn't exist.
    try:
        os.mkdir(TEMP_DIR)
    except FileExistsError:
        pass

    # Input source file.
    source = os.path.join(SOURCE_DIR, name + ".asm")

    # Output files for the assembler.
    targets = [
        {
            "output" : os.path.join(TEMP_DIR, "patch-" + name + "-fill00.bin"),
            "options" : ["-d", "filler=0"],
            "data" : None,
        },
        {
            "output" : os.path.join(TEMP_DIR, "patch-" + name + "-fillFF.bin"),
            "options" : ["-d", "filler=255"],
            "data" : None,
        },
    ]

    # Run the assembler and collect its output.
    for target in targets:
        try:
            subprocess.run([bass_path] + target["options"] + ["-strict", "-o", target["output"], source], check=True)
        except subprocess.CalledProcessError as e:
            print()  # makes error from the assembler easier to read
            raise AssemblerError(e)

        try:
            # Read file.
            with open(target["output"], "rb") as f:
                target["data"] = f.read()
        except OSError as e:
            raise AssemblerError(e)

        # Delete file, since we don't need it anymore.
        try:
            os.remove(target["output"])
        except OSError:
            # Don't care if this deletion fails.
            pass

    # Find the byte ranges that are the same, meaning they are patched.
    data00 = targets[0]["data"]
    dataFF = targets[1]["data"]
    patched_ranges = []
    run_start = None

    for i in range(new_rom_size):
        if data00[i] == dataFF[i]:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                patched_ranges += [[run_start, i - run_start]]
                run_start = None
    if run_start is not None:
        patched_ranges += [[run_start, i - run_start]]

    if patched_ranges:
        raise AssemblerError("No data patched!")

    # Verify the format of the export table.
    try:
        decode_export_table(DecodeBuffer(data00, new_rom_size, len(data00) - new_rom_size))
    except PatchFormatError as e:
        raise AssemblerError(e)

    # Build the serialized patch file.
    patch_entry_encoder = struct.Struct(PATCH_ENTRY_FORMAT)
    patch_data = bytearray()
    patch_data += PATCH_MAGIC
    patch_data += name.encode("utf-8") + b"\0"
    patch_data += struct.pack("<I", len(patched_ranges))
    # Patch data.
    for patch in patched_ranges:
        patch_data += patch_entry_encoder.pack(patch[0], patch[1])
        patch_data += data00[patch[0] : patch[0] + patch[1]]
    # Export table.
    patch_data += data00[new_rom_size : ]

    # Verify that decoding works.
    patch_object = decode_patch(DecodeBuffer(patch_data, 0, len(patch_data)))

    # Write the patch to the output file.
    with open(os.path.join(PATCH_DIR, name + PATCH_EXTENSION), "wb") as fout:
        fout.write(patch_data)

    # Return the patch object, in case it's wanted.
    return patch_object


# Loads the patch listfile.
def load_patch_list_file():
    patch_list = []
    with open(PATCH_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            # Remove comments and leading/trailing whitespace.
            line = line.partition(";")[0].strip()
            if line != "":
                patch_list += [line]
    return patch_list



# Builds a set of patches.
def build_patch_set(patch_list, new_rom_size):
    print()

    # Find the bass to use.
    bass = get_assembler_path(ASSEMBLER_BASS)

    # Iterate over the list of patches.
    for name in patch_list:
        print("Building %s..." % name)
        build_65816_patch(name, bass, new_rom_size)

    print("Done building patches.")
    print()


# Build all patches.
def build_all_patches(new_rom_size):
    build_patch_set(load_patch_list_file(), new_rom_size)


# Patch manager object.
class AssemblyPatchDB:
    def __init__(self):
        self.patches = {}
    def __str__(self):
        return str(self.patches)
    # Allows [] syntax to get patches.
    def __getitem__(self, name):
        return self.patches[name]
    # Shortcut function for most use cases.
    def apply_patch(self, fout, patch_name):
        self.patches[patch_name].write(fout)


# Loads all patches.
def load_all_patches():
    patches = AssemblyPatchDB()
    patch_list = load_patch_list_file()
    for name in patch_list:
        patches.patches[name] = load_patch(os.path.join(PATCH_DIR, name + PATCH_EXTENSION))
    return patches
