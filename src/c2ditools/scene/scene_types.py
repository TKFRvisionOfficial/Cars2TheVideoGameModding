import struct
from typing import Literal, BinaryIO
from ..utils import get_str_endianness

MAGIC_SIZE = 12
HEADER_STRUCT = "II"
HEADER_SIZE = struct.calcsize(HEADER_STRUCT)

ENDIAN_MAGIC = {
    "big": bytes.fromhex("45 01 76 29 3F 8C CC CD 00 00 00 00"),
    "little": bytes.fromhex("29 76 01 45 CD CC 8C 3F 00 00 00 00")
}

MAGIC_ENDIAN = {magic: endianness for endianness, magic in ENDIAN_MAGIC.items()}


class SceneHeader:
    def __init__(self, magic: bytes, string_table_size: int, tree_size: int, endianness: Literal["big", "little"]):
        self.endianness = endianness
        self.magic = magic
        self.string_table_size = string_table_size
        self.tree_size = tree_size

    @staticmethod
    def get_size() -> int:
        return MAGIC_SIZE + HEADER_SIZE + struct.calcsize("40x")

    @classmethod
    def from_file(cls, input_stream: BinaryIO):
        magic = input_stream.read(12)
        endianness = MAGIC_ENDIAN.get(magic)
        if endianness is None:
            raise ValueError(f"Unknown magic {magic.hex()}.")

        string_table_size, tree_size = struct.unpack(get_str_endianness(endianness) + HEADER_STRUCT, input_stream.read(HEADER_SIZE))
        input_stream.read(40)  # padding...hopefully
        return cls(magic, string_table_size, tree_size, endianness)

    def to_bytes(self) -> bytes:
        return ENDIAN_MAGIC[self.endianness] + \
               struct.pack(get_str_endianness(self.endianness) + HEADER_STRUCT + "40x", self.string_table_size, self.tree_size)

