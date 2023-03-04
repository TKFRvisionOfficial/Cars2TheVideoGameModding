import struct
from typing import BinaryIO
from ..utils import get_str_endianness, Endianness

ENDIAN_MAGIC = {
    "big": bytes.fromhex("45 01 76 29 3F 8C CC CD 00 00 00 00"),
    "little": bytes.fromhex("29 76 01 45 CD CC 8C 3F 00 00 00 00")
}

MAGIC_ENDIAN = {magic: endianness for endianness, magic in ENDIAN_MAGIC.items()}


class SceneHeader:
    _STRUCT_STR = "12sII40x"

    def __init__(self, string_table_size: int, tree_size: int, endianness: Endianness):
        self.endianness = endianness
        self.string_table_size = string_table_size
        self.tree_size = tree_size

    @classmethod
    def get_size(cls) -> int:
        return struct.calcsize(cls._STRUCT_STR)

    @classmethod
    def from_file(cls, input_stream: BinaryIO) -> "SceneHeader":
        magic = input_stream.read(12)
        endianness = MAGIC_ENDIAN.get(magic)
        if endianness is None:
            raise ValueError(f"Unknown magic {magic.hex()}.")

        magic, string_table_size, tree_size = struct.unpack(get_str_endianness(endianness) + cls._STRUCT_STR,
                                                            magic + input_stream.read(cls.get_size() - 12))
        return cls(string_table_size, tree_size, endianness)

    def to_bytes(self) -> bytes:
        return struct.pack(get_str_endianness(self.endianness) + self._STRUCT_STR,
                           ENDIAN_MAGIC[self.endianness],
                           self.string_table_size,
                           self.tree_size)


class SceneNode:
    def __init__(self, level: int, type_int: int, str_index: int):
        self.level = level
        self.type_int = type_int
        self.str_index = str_index

    def to_bytes(self, endianness: Endianness) -> bytes:
        # 6 bits level and then 10 bit type_int
        return (self.level << 10 | self.type_int).to_bytes(2, endianness, signed=False) \
               + self.str_index.to_bytes(2, endianness, signed=False)

    @classmethod
    def from_bytes(cls, data: bytes, endianness: Endianness) -> "SceneNode":
        level, type_int = divmod(int.from_bytes(data[:2], endianness), 0x400)
        str_index = int.from_bytes(data[2:], endianness)
        return cls(level, type_int, str_index)

    @staticmethod
    def get_size() -> int:
        return 4
