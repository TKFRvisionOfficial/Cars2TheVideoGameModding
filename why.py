#
# Based on the research of the amazing "Teancum".
# Written by TKFRvision (https://github.com/tkfrvisionofficial)
# All Rights reserved
#

import struct
import zipfile
import tempfile
import shutil
import os
from typing import BinaryIO
import hashlib


MD5_HEADER = struct.pack("7B", 75, 70, 19, 0, 77, 68, 53)  # from an original file


class ZipEndLocator:
    def __init__(self, signature: int, disk_number: int, start_disk_number: int, entries_on_disk: int,
                 total_entries: int, directory_size: int, directory_offset: int, comment: str):
        self.signature = signature
        self.disk_number = disk_number
        self.start_disk_number = start_disk_number
        self.entries_on_disk = entries_on_disk
        self.total_entries = total_entries
        self.directory_size = directory_size
        self.directory_offset = directory_offset
        self.comment = comment

    @classmethod
    def from_file(cls, file: BinaryIO, header_offset: int):
        file.seek(header_offset)

        data = file.read(20)  # until comment length
        comment_length = int.from_bytes(file.read(2), "little")
        comment = file.read(comment_length).decode("utf-8")

        return cls(*struct.unpack("<IHHHHII", data), comment)

    def to_bytes(self) -> bytes:
        comment_bytes = self.comment.encode("utf-8")
        comment_length = len(comment_bytes)
        return struct.pack(f"<IHHHHIIH{comment_length}s", self.signature, self.disk_number, self.start_disk_number,
                           self.entries_on_disk, self.total_entries, self.directory_size, self.directory_offset,
                           comment_length, comment_bytes)


class ZipDirEntry:
    def __init__(self, signature: int, version_made_by: int, version_to_extract: int, flags: int, compression: int,
                 file_time: int, file_date: int, crc32: int, compressed_size: int, uncompressed_size: int,
                 disk_number_start: int, internal_attributes: int, external_attributes: int, header_offset: int,
                 file_name: str, extra_field: bytes, comment: str):
        self.signature = signature
        self.version_made_by = version_made_by
        self.version_to_extract = version_to_extract
        self.flags = flags
        self.compression = compression
        self.file_time = file_time
        self.file_date = file_date
        self.crc32 = crc32
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size
        self.disk_number_start = disk_number_start
        self.internal_attributes = internal_attributes
        self.external_attributes = external_attributes
        self.header_offset = header_offset
        self.file_name = file_name
        self.extra_field = extra_field
        self.comment = comment

    @classmethod
    def from_file(cls, file: BinaryIO, header_offset: int = None):
        if header_offset:
            file.seek(header_offset)

        data0 = file.read(28)  # until lengths
        file_name_length, extra_field_length, comment_length = struct.unpack("<HHH", file.read(6))
        data1 = file.read(12)  # until length fields with dynamic lengths

        file_name = file.read(file_name_length).decode("utf-8")
        extra_field = file.read(extra_field_length)
        comment = file.read(comment_length).decode("utf-8")

        return cls(*struct.unpack("<IHHHHHHIII", data0), *struct.unpack("<HHII", data1), file_name, extra_field, comment)

    def to_bytes(self) -> bytes:
        file_name_bytes = self.file_name.encode("utf-8")
        file_name_length = len(file_name_bytes)
        extra_field_length = len(self.extra_field)
        comment_bytes = self.comment.encode("utf-8")
        comment_length = len(comment_bytes)

        return struct.pack(f"<I6H3I3H2H2I{file_name_length}s{extra_field_length}s{comment_length}s",
                           self.signature, self.version_made_by, self.version_to_extract, self.flags,
                           self.compression, self.file_time, self.file_date, self.crc32, self.compressed_size,
                           self.uncompressed_size, file_name_length, extra_field_length, comment_length,
                           self.disk_number_start, self.internal_attributes, self.external_attributes,
                           self.header_offset, file_name_bytes, self.extra_field, comment_bytes)


def hash_md5(path: str) -> bytes:
    md5_hash = hashlib.md5()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)
    return MD5_HEADER + md5_hash.digest()


def chunk_iter(file: BinaryIO, end: int, step: int = 4096):
    while (distance_to_end := end - file.tell()) > 0:
        if distance_to_end >= step:
            yield file.read(step)
        else:
            yield file.read(distance_to_end)


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
        md5_hashes = {}
        tmp_zip_path = os.path.join(tmp_dir, "archive.zip")
        with zipfile.ZipFile(tmp_zip_path, "w") as tmp_file:
            for folder_name, _, filenames in os.walk(in_folder):
                for filename in filenames:
                    file_path = os.path.join(folder_name, filename)
                    internal_path = os.path.relpath(file_path, in_folder).replace("\\", "/")
                    md5_hashes[internal_path] = hash_md5(file_path)
                    tmp_file.write(file_path, internal_path, zipfile.ZIP_DEFLATED)

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


if __name__ == '__main__':
    import argparse

    _arg_parser = argparse.ArgumentParser(
        prog="why(.py) did we bother. Written by TKFRvision",
        description="A programm to pack zips for Cars 2: The Videogame",
        epilog="https://github.com/TKFRvisionOfficial/Cars2TheVideoGameModding/blob/main/why.py",
    )
    _arg_parser.add_argument("in_folder", help="The files of this folder will get packed.")
    _arg_parser.add_argument("out_file", help="The destination of the file that will be generated.")
    _args = _arg_parser.parse_args()

    assert os.path.isdir(_args.in_folder), "folder is not valid"
    assert not os.path.isdir(_args.out_file), "file destination is not valid"

    main(_args.in_folder, _args.out_file)
