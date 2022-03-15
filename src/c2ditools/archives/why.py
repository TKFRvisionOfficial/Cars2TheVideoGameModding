#
# Based on the research of the amazing "aluigi".
# Written by TKFRvision (https://github.com/tkfrvisionofficial)
# All Rights reserved
#

import os
import shutil
import tempfile
from typing import BinaryIO, Sequence

from ..utils import chunk_iter
from .archive_utils import ZipDirEntry, ZipEndLocator, create_md5_zip


def update_and_write_dir_entries(file_from: BinaryIO, file_to: BinaryIO, from_loc: int, to_loc: int,
                                 md5_hashes: dict, to_add: int):
    file_from.seek(from_loc)
    while file_from.tell() < to_loc:
        zip_dir_entry = ZipDirEntry.from_file(file_from)
        zip_dir_entry.header_offset += to_add
        zip_dir_entry.extra_field = md5_hashes[zip_dir_entry.file_name]
        zip_dir_entry.external_attributes = 0  # overwriting them because orig files doesn't have them
        file_to.write(zip_dir_entry.to_bytes())


def main(in_folder: str, out_file: str):
    tmp_dir = tempfile.mkdtemp()
    try:
        # Build normal archive and generate md5 hashes
        tmp_zip_path = os.path.join(tmp_dir, "archive.zip")
        md5_hashes = create_md5_zip(tmp_zip_path, in_folder)

        # Build "funky" archive
        with open(tmp_zip_path, "rb") as tmp_file, open(out_file, "wb") as final_file:
            # need to add comment support here
            zip_end_locator_offset = os.path.getsize(tmp_zip_path) - 22
            zip_end_locator = ZipEndLocator.from_file(tmp_file, zip_end_locator_offset)

            # calculate amount to add to the offsets
            size_of_md5_fields = zip_end_locator.total_entries * 23  # md5 bytes + header
            add_offset = (os.path.getsize(tmp_zip_path) - zip_end_locator.directory_offset) + size_of_md5_fields

            # writing 1st end locators
            tmp_file_directory_offset = zip_end_locator.directory_offset
            zip_end_locator.directory_offset += add_offset
            zip_end_locator.directory_size += size_of_md5_fields
            final_file.write(zip_end_locator.to_bytes())

            # writing 1st dir entries
            update_and_write_dir_entries(tmp_file, final_file, tmp_file_directory_offset, zip_end_locator_offset,
                                         md5_hashes, add_offset)

            # writing file records
            tmp_file.seek(0)  # maybe make that not 0
            for chunk in chunk_iter(tmp_file, tmp_file_directory_offset):
                final_file.write(chunk)

            # write 2nd dir entries
            update_and_write_dir_entries(tmp_file, final_file, tmp_file_directory_offset, zip_end_locator_offset,
                                         md5_hashes, add_offset)

            # write 2nd end locator
            final_file.write(zip_end_locator.to_bytes())

    finally:
        shutil.rmtree(tmp_dir)


def run_from_args(args: Sequence[str]):
    import argparse

    _arg_parser = argparse.ArgumentParser(
        prog="why(.py) did we bother. Written by TKFRvision",
        description="A program to pack zips for Cars 2: The Video Game",
    )
    _arg_parser.add_argument("in_folder", help="The files of this folder will get packed.")
    _arg_parser.add_argument("out_file", help="The destination of the file that will be generated.")
    _args = _arg_parser.parse_args(args)

    assert os.path.isdir(_args.in_folder), "folder is not valid"
    assert not os.path.isdir(_args.out_file), "file destination is not valid"

    main(_args.in_folder, _args.out_file)
