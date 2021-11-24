#
# Written by TKFRvision
# VERY EARLY WORK IN PROGRESS --> NOT WORKING
#

import os
import struct
import functools
import argparse
from typing import BinaryIO

HEADER_SIZE = 0x80 * 80  # 0x80 headers are always used... todo make this dynamic depending on data size
_TEXTURE_HEADER_STRUCT = ">III"


class TextureHeaderEntry:
    def __init__(self, thb_offset: int, tbb_offset: int, texture_size: int):
        self.thb_offset = thb_offset
        self.tbb_offset = tbb_offset
        self.texture_size = texture_size

    @classmethod
    def from_stream(cls, binary_stream: BinaryIO):
        return cls(*struct.unpack(_TEXTURE_HEADER_STRUCT, binary_stream.read(struct.calcsize(_TEXTURE_HEADER_STRUCT))))

    @classmethod
    def get_entries_from_stream(cls, binary_stream: BinaryIO):
        binary_stream.seek(0)
        entries = []
        for _ in range(int.from_bytes(binary_stream.read(4), "big", signed=False)):
            entries.append(cls.from_stream(binary_stream))
        return entries

    def to_stream(self, binary_stream: BinaryIO):
        binary_stream.write(struct.pack(_TEXTURE_HEADER_STRUCT, self.thb_offset, self.tbb_offset, self.texture_size))


parser = argparse.ArgumentParser()
parser.add_argument("thb_file")
parser.add_argument("tbb_file")
parser.add_argument("tstream_dir")
parser.add_argument("output_file")
args = parser.parse_args()


with open(args.output_file, "wb") as des_file, open(args.thb_file, "rb") as thb_file, \
        open(args.tbb_file, "rb") as tbb_file:
    # get thb_header entries
    thb_header_entries = TextureHeaderEntry.get_entries_from_stream(thb_file)
    # gtf version
    des_file.write(b"\x02\x01\x01\xFF")
    # size of all textures (0x48 is padding)
    des_file.write((functools.reduce(lambda final, cur: final + cur.texture_size, thb_header_entries, 0) + 0x48 * len(thb_header_entries)).to_bytes(4, "big", signed=False))
    # number of textures
    des_file.write(len(thb_header_entries).to_bytes(4, "big", signed=False))

    tstreams = {}
    all_tstreams_size = 0
    for index, thb_header_entry in enumerate(thb_header_entries):
        # index of texture
        des_file.write(index.to_bytes(4, "big", signed=False))

        # checking for tstream
        thb_file.seek(thb_header_entry.thb_offset)

        tstream_size = 0
        extra_fields = int.from_bytes(thb_file.read(4), "big", signed=False)
        if extra_fields > 1:
            for tstream_file_name in os.listdir(args.tstream_dir):
                if f"_{index}.tstream" in tstream_file_name:
                    tstream_path = os.path.join(args.tstream_dir, tstream_file_name)
                    tstream_size = os.path.getsize(tstream_path)
                    tstreams[index] = tstream_path
                    break
            if tstream_size == 0:
                print(f"WARNING TSTREAM FOR TEXTURE {index} EXPECTED BUT NOT FOUND.")

        # texture offset (0x48 is padding)
        des_file.write((thb_header_entry.tbb_offset + HEADER_SIZE + 0x48 * index + all_tstreams_size).to_bytes(4, "big", signed=False))
        # des_file.write((thb_header_entry.tbb_offset + HEADER_SIZE + 0x38 * index + all_tstreams_size).to_bytes(4, "big", signed=False))
        all_tstreams_size += tstream_size
        # des_file.write((thb_header_entry.tbb_offset + HEADER_SIZE + 0x48 * index).to_bytes(4, "big", signed=False))

        # texture size
        des_file.write((thb_header_entry.texture_size + tstream_size).to_bytes(4, "big", signed=False))
        # des_file.write((thb_header_entry.texture_size).to_bytes(4, "big", signed=False))

        # skipping extra field count and texture size. we ignoring the extra fields because I dont know what they do...
        thb_file.seek(thb_header_entry.thb_offset + 8)
        des_file.write(thb_file.read(24))

    # writing zero bytes till the end of the header
    size_to_header_end = HEADER_SIZE - des_file.tell()
    assert size_to_header_end >= 0, "header too small"
    des_file.write(b"\x00" * size_to_header_end)

    # writing textures
    for index, thb_header_entry in enumerate(thb_header_entries):
        if index in tstreams.keys():
            with open(tstreams[index], "rb") as tstream_file:
                des_file.write(tstream_file.read())
        tbb_file.seek(thb_header_entry.tbb_offset)
        des_file.write(tbb_file.read(thb_header_entry.texture_size))
        # adding padding
        des_file.write(b"\x00" * 0x48)
        # des_file.write(tbb_file.read(0x48))
