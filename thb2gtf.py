#
# Written by TKFRvision
# All Rights Reserved
#

import functools
import itertools
import os
import struct
import json

from thb_stuff import TextureHeaderEntry

_HEADER_SIZE = 0x80 * 80  # 0x80 headers are always used... todo make this dynamic depending on data size

# _PADDING = 0x48
_PADDING = 0


def main(thb_file_path: str, tbb_file_path: str, tstream_folder_path: str, output_file_path: str, json_output: str):
    with open(output_file_path, "wb") as des_file, open(thb_file_path, "rb") as thb_file,\
            open(tbb_file_path, "rb") as tbb_file:
        # get thb_header entries
        thb_header_entries = TextureHeaderEntry.get_entries_from_stream(thb_file)
        # gtf version
        des_file.write(b"\x02\x01\x01\xFF")
        # size of all textures (0x48 is padding)
        des_file.write((functools.reduce(lambda final, cur: final + cur.texture_size, thb_header_entries, 0) + _PADDING * len(thb_header_entries)).to_bytes(4, "big", signed=False))
        # number of textures
        des_file.write(len(thb_header_entries).to_bytes(4, "big", signed=False))

        tstreams = {}
        json_tstream = []
        all_tstreams_size = 0
        for index, thb_header_entry, cur_offset in zip(itertools.count(), thb_header_entries, itertools.accumulate(thb_header_entries, lambda final, cur: final + cur.texture_size, initial=0)):
            # index of texture
            des_file.write(index.to_bytes(4, "big", signed=False))

            # checking for tstream
            thb_file.seek(thb_header_entry.thb_offset)

            tstream_size = 0
            extra_fields = int.from_bytes(thb_file.read(4), "big", signed=False)
            # only one "tstream field" means no tstream file
            # if you want to know more about the extra fields refer to the comment in gtf2thb.py
            if extra_fields > 1:
                for tstream_file_name in os.listdir(tstream_folder_path):
                    if f"_{index}.tstream" in tstream_file_name:
                        tstream_path = os.path.join(tstream_folder_path, tstream_file_name)
                        tstream_size = os.path.getsize(tstream_path)
                        # reading extra fields (ignoring the first one because its always 0)
                        thb_file.seek(thb_header_entry.thb_offset + 0x24)
                        json_tstream.append({
                            "texture_index": index,
                            "extra_fields": struct.unpack(f">{extra_fields-1}I", thb_file.read((extra_fields-1) * 4))
                        })
                        tstreams[index] = tstream_path
                        break
                if tstream_size == 0:
                    print(f"WARNING TSTREAM FOR TEXTURE {index} EXPECTED BUT NOT FOUND.")

            # texture offset (0x48 is padding)
            des_file.write((cur_offset + _HEADER_SIZE + _PADDING * index + all_tstreams_size).to_bytes(4, "big", signed=False))
            all_tstreams_size += tstream_size

            # texture size
            des_file.write((thb_header_entry.texture_size + tstream_size).to_bytes(4, "big", signed=False))

            # skipping tstream field count and texture size
            thb_file.seek(thb_header_entry.thb_offset + 8)
            des_file.write(thb_file.read(24))

        # writing zero bytes till the end of the header
        size_to_header_end = _HEADER_SIZE - des_file.tell()
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
            des_file.write(b"\x00" * _PADDING)

        # creating json
        with open(json_output, "w", encoding="utf-8") as json_file:
            json.dump(json_tstream, json_file, ensure_ascii=False, indent="\t", sort_keys=False)


if __name__ == '__main__':
    import argparse

    _parser = argparse.ArgumentParser(
        prog="thb2gtf.py. does what the name says dummy... Written by TKFRvision"
    )
    _parser.add_argument("thb_file")
    _parser.add_argument("tbb_file")
    _parser.add_argument("tstream_dir")
    _parser.add_argument("output_file")
    _parser.add_argument("output_json")
    _args = _parser.parse_args()

    main(_args.thb_file, _args.tbb_file, _args.tstream_dir, _args.output_file, _args.output_json)
