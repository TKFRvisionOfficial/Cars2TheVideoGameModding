#
# Written by TKFRvision
# All Rights Reserved
#

import os
import struct
import json
from typing import List, Dict, Union, BinaryIO, Iterable
import itertools

from thb_stuff import TextureHeaderEntry, TEXTURE_HEADER_SIZE

_GTF_HEADER_STRUCT = ">3I"
GTF_HEADER_SIZE = struct.calcsize(_GTF_HEADER_STRUCT)
_GTF_HEADER_ENTRY_STRUCT = ">3I24s"
GTF_HEADER_ENTRY_SIZE = struct.calcsize(_GTF_HEADER_ENTRY_STRUCT)


class GtfHeaderEntry:
    def __init__(self, index: int, texture_offset: int, texture_size: int, content: bytes):
        self.index = index
        self.texture_offset = texture_offset
        self.texture_size = texture_size
        self.content = content

    @classmethod
    def from_stream(cls, input_stream: BinaryIO):
        return cls(*struct.unpack(_GTF_HEADER_ENTRY_STRUCT, input_stream.read(GTF_HEADER_ENTRY_SIZE)))

    def to_bytes(self) -> bytes:
        return struct.pack(_GTF_HEADER_ENTRY_STRUCT, self.index, self.texture_offset, self.texture_size, self.content)


class GtfHeader:
    def __init__(self, version: int, size: int, amount_textures: int, header_entries: List[GtfHeaderEntry]):
        self.version = version
        self.size = size
        self.amount_textures = amount_textures
        self.header_entries = header_entries

    @classmethod
    def from_stream(cls, input_stream: BinaryIO):
        version, size, amount_textures = struct.unpack(_GTF_HEADER_STRUCT, input_stream.read(GTF_HEADER_SIZE))
        header_entries = [GtfHeaderEntry.from_stream(input_stream) for _ in range(amount_textures)]
        return cls(version, size, amount_textures, header_entries)

    def to_bytes(self) -> bytes:
        return struct.pack(_GTF_HEADER_STRUCT, self.version, self.size, self.amount_textures) \
               + b"".join(header_entry.to_bytes() for header_entry in self.header_entries)


def main(gtf_file_path: str, json_file_path: str, thb_file_path: str, tbb_file_path: str, tstream_folder: str):
    # reading json
    with open(json_file_path, "r", encoding="utf-8") as json_file:
        json_tstream: List[Dict[str, Union[str, List[int]]]] = json.load(json_file)

    with open(gtf_file_path, "rb") as gtf_file, open(thb_file_path, "wb") as thb_file, \
            open(tbb_file_path, "wb") as tbb_file:

        gtf_header = GtfHeader.from_stream(gtf_file)
        # the 4 is the field containing the amount of textures
        header_size = TEXTURE_HEADER_SIZE * gtf_header.amount_textures + 4

        # amount of textures
        thb_file.write(gtf_header.amount_textures.to_bytes(4, "big"))
        # filling the header with null bytes (we are already past the amount of textures)
        thb_file.write(b"\x00" * (header_size - 4))
        thb_file.seek(4)
        # convert header
        for header_entry in gtf_header.header_entries:
            tbb_texture_offset = tbb_file.tell()
            gtf_file.seek(header_entry.texture_offset)  # is that wrong?
            try:
                # The extra fields in the thb tells the game if and where mipmap levels are located in tstream.
                # If there is more then one extra field the games expects a tstream. Tstreams get created
                # if there a mipmap levels in a texture that have a higher resolution then 128x128. Maybe its also/or
                # dependent on size. The numbers in the extra field are the location where the mip map levels start
                # in the tstream. The rest of the mip map levels are from the thb. The last number in the extra fields
                # is the (theoretical) offset where the tbb mip map levels start. That also means that they contain
                # the size of the tstream. The first extra field is ignored because its always 0. It isn't in the
                # json from thb2gtf at all.

                tstream_data = next(filter(lambda entry: entry["texture_index"] == header_entry.index, json_tstream))
                tstream_size = tstream_data["extra_fields"][-1]
                with open(tstream_folder % header_entry.index, "wb") as tstream_file:
                    tstream_file.write(gtf_file.read(tstream_size))
                tbb_texture_size = header_entry.texture_size - tstream_size
            except StopIteration:   # no tstream
                tstream_data = None
                tbb_texture_size = header_entry.texture_size
            tbb_file.write(gtf_file.read(tbb_texture_size))

            thb_header_offset = thb_file.tell()

            # writing next data chunk at end of file
            thb_file.seek(0, os.SEEK_END)
            thb_offset = thb_file.tell()
            if tstream_data:
                thb_file.write((len(tstream_data["extra_fields"]) + 1).to_bytes(4, "big"))
            else:
                thb_file.write((1).to_bytes(4, "big"))
            thb_file.write(header_entry.texture_size.to_bytes(4, "big"))
            thb_file.write(header_entry.content)
            # always 0 extra field
            thb_file.write((0).to_bytes(4, "big"))
            # extra fields from json
            if tstream_data:
                for extra_field in tstream_data["extra_fields"]:
                    thb_file.write(extra_field.to_bytes(4, "big"))

            # writing header entry
            thb_file.seek(thb_header_offset)
            thb_file.write(TextureHeaderEntry(thb_offset, tbb_texture_offset, tbb_texture_size).to_bytes())


if __name__ == '__main__':
    import argparse

    _parser = argparse.ArgumentParser()
    _parser.add_argument("gtf")
    _parser.add_argument("json")
    _parser.add_argument("thb")
    _parser.add_argument("tbb")
    _parser.add_argument("tstream")
    _args = _parser.parse_args()

    main(_args.gtf, _args.json, _args.thb, _args.tbb, _args.tstream)
