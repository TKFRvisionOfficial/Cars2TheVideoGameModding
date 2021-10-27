#
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


MD5_HEADER = struct.pack("7B", 75, 70, 19, 0, 77, 68, 53)


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


def edit_and_write_zip_end_locators(file_from: BinaryIO, file_to: BinaryIO, from_loc: int, to_loc: int,
                                    md5_hashes: dict, to_add: int):
    file_from.seek(from_loc)
    while file_from.tell() < to_loc:
        zip_dir_entry = ZipDirEntry.from_file(file_from)
        zip_dir_entry.header_offset += to_add
        zip_dir_entry.extra_field = md5_hashes[zip_dir_entry.file_name]
        zip_dir_entry.external_attributes = 0  # overwriting them because orig files dosen't have them
        file_to.write(zip_dir_entry.to_bytes())


_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Cars 2\backup\mcqueen"
_tmp_dir = tempfile.mkdtemp()
try:
    # Build normal archive and create md5 hashes
    _md5_hashes = {}
    _tmp_zip_path = os.path.join(_tmp_dir, "archive.zip")
    with zipfile.ZipFile(_tmp_zip_path, "w") as _tmp_file:
        for _folder_name, _, _filenames in os.walk(_PATH):
            for _filename in _filenames:
                _file_path = os.path.join(_folder_name, _filename)
                _internal_path = os.path.relpath(_file_path, _PATH).replace("\\", "/")
                _md5_hashes[_internal_path] = hash_md5(_file_path)
                _tmp_file.write(_file_path, _internal_path, zipfile.ZIP_DEFLATED)

        _zip_info = zipfile.ZipInfo.from_file(_tmp_zip_path)
        # _zip_end_locator_offset = _tmp_file.header_offset
    # Build "funky" archive
    with open(_tmp_zip_path, "rb") as _tmp_file, open("frick.zip", "wb") as _final_file:
        # need to add comment support here
        _zip_end_locator_offset = os.path.getsize(_tmp_zip_path) - 22

        _zip_end_locator = ZipEndLocator.from_file(_tmp_file, _zip_end_locator_offset)

        # _add_offset = len(_zip_end_locator.to_bytes()) + _zip_end_locator.total_entries * 23   # md5 is 23 bytes
        _add_offset = (os.path.getsize(_tmp_zip_path) - _zip_end_locator.directory_offset) + _zip_end_locator.total_entries * 23  # md5 is 23 bytes

        _old_directory_offset = _zip_end_locator.directory_offset
        _zip_end_locator.directory_offset += _add_offset
        _final_file.write(_zip_end_locator.to_bytes())

        edit_and_write_zip_end_locators(_tmp_file, _final_file, _old_directory_offset, _zip_end_locator_offset,
                                        _md5_hashes, _add_offset)

        _tmp_file.seek(0)  # maybe make that not 0
        for _chunk in chunk_iter(_tmp_file, _old_directory_offset):
            _final_file.write(_chunk)

        edit_and_write_zip_end_locators(_tmp_file, _final_file, _old_directory_offset, _zip_end_locator_offset,
                                        _md5_hashes, _add_offset)
        _final_file.write(_zip_end_locator.to_bytes())


finally:
    shutil.rmtree(_tmp_dir)
