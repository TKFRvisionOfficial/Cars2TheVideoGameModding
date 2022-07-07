import struct
from typing import BinaryIO

_TEXTURE_HEADER_STRUCT = ">III"
TEXTURE_HEADER_SIZE = struct.calcsize(_TEXTURE_HEADER_STRUCT)


class TextureHeaderEntry:
    def __init__(self, thb_offset: int, tbb_offset: int, texture_size: int):
        self.thb_offset = thb_offset
        self.tbb_offset = tbb_offset
        self.texture_size = texture_size

    @classmethod
    def from_stream(cls, binary_stream: BinaryIO):
        return cls(*struct.unpack(_TEXTURE_HEADER_STRUCT, binary_stream.read(TEXTURE_HEADER_SIZE)))

    @classmethod
    def get_entries_from_stream(cls, binary_stream: BinaryIO):
        binary_stream.seek(0)
        entries = []
        for _ in range(int.from_bytes(binary_stream.read(4), "big", signed=False)):
            entries.append(cls.from_stream(binary_stream))
        return entries

    def to_bytes(self) -> bytes:
        return struct.pack(_TEXTURE_HEADER_STRUCT, self.thb_offset, self.tbb_offset, self.texture_size)
