#   Copyright 2024 TKFRvision
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import struct
from typing import BinaryIO, Sequence, Tuple, Dict
from Crypto.Cipher._mode_ctr import CtrMode
from Crypto.Cipher import AES
import hashlib
import os
import zipfile

MD5_HEADER = struct.pack("7B", 75, 70, 19, 0, 77, 68, 53)  # from an original file
ENC_KEY = b"\x68\x1B\xBE\xEA\x63\x16\x01\x88\xF9\xB7\x94\x51\x04\xA5\x14\x99"


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
    _STRUCT_STR = f"<I6H3I3H2H2I"

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

        return cls(*struct.unpack("<IHHHHHHIII", data0), *struct.unpack("<HHII", data1), file_name, extra_field,
                   comment)

    def to_bytes(self) -> bytes:
        file_name_bytes = self.file_name.encode("utf-8")
        file_name_length = len(file_name_bytes)
        extra_field_length = len(self.extra_field)
        comment_bytes = self.comment.encode("utf-8")
        comment_length = len(comment_bytes)

        return struct.pack(self._STRUCT_STR,
                           self.signature, self.version_made_by, self.version_to_extract, self.flags,
                           self.compression, self.file_time, self.file_date, self.crc32, self.compressed_size,
                           self.uncompressed_size, file_name_length, extra_field_length, comment_length,
                           self.disk_number_start, self.internal_attributes, self.external_attributes,
                           self.header_offset) + file_name_bytes + self.extra_field + comment_bytes


class EncFileEntry:
    _STRUCT_STR = "<LL"

    def __init__(self, name_crc: int, offset: int):
        self.name_crc = name_crc
        self.offset = offset

    def to_bytes(self) -> bytes:
        return struct.pack(self._STRUCT_STR, self.name_crc, self.offset)

    @classmethod
    def get_size(cls) -> int:
        return struct.calcsize(cls._STRUCT_STR)


class EncFileHeader:
    _STRUCT_STR = "<L"
    _MAGIC = b"PK\xff\xff"

    def __init__(self, file_entries: Sequence[EncFileEntry]):
        self.file_entries = file_entries

    def to_bytes(self) -> bytes:
        length = struct.pack(self._STRUCT_STR, len(self.file_entries))
        data = b"".join(file_entry.to_bytes() for file_entry in self.file_entries)
        return self._MAGIC + length + data

    def to_bytes_enc(self) -> bytes:
        cipher = AES.new(ENC_KEY, AES.MODE_CTR, nonce=b"")
        return cipher.encrypt(self.to_bytes())

    @classmethod
    def get_size_without_str(cls) -> int:
        return len(cls._MAGIC) + struct.calcsize(cls._STRUCT_STR)

    def get_size(self):
        return self.get_size_without_str() + EncFileEntry.get_size() * len(self.file_entries)


class ZipFileRecord:
    _STRUCT_STR = "<4s5H3I2H"
    _MAGIC = b'PK\x03\x04'

    def __init__(self, ver: int, flag: int, method: int, mod_time: int, mod_date: int,
                 crc32: int, comp_size: int, uncomp_size: int, name: str, extra: bytes):
        self.ver = ver
        self.flag = flag
        self.method = method
        self.mod_time = mod_time
        self.mod_date = mod_date
        self.crc32 = crc32
        self.comp_size = comp_size
        self.uncomp_size = uncomp_size
        self.name = name
        self.extra = extra

    @classmethod
    def from_file(cls, input_stream: BinaryIO):
        magic, ver, flag, method, mod_time, mod_date, crc32, comp_size, uncomp_size, name_length, extra_length = \
            struct.unpack(cls._STRUCT_STR, input_stream.read(struct.calcsize(cls._STRUCT_STR)))
        name = input_stream.read(name_length).decode("utf-8")
        extra = input_stream.read(extra_length)
        return cls(ver, flag, method, mod_time, mod_date, crc32, comp_size, uncomp_size, name, extra)

    def to_bytes(self) -> bytes:
        return struct.pack(self._STRUCT_STR, self._MAGIC, self.ver, self.flag, self.method, self.mod_time,
                           self.mod_date, self.crc32, self.comp_size, self.uncomp_size, len(self.name),
                           len(self.extra)) + self.name.encode("utf-8") + self.extra

    def to_bytes_enc(self) -> Tuple[bytes, CtrMode]:
        # probably not needed
        cipher = AES.new(ENC_KEY, AES.MODE_CTR, nonce=b"")
        return cipher.encrypt(self.to_bytes()), cipher


def hash_md5(path: str) -> bytes:
    md5_hash = hashlib.md5()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)
    return MD5_HEADER + md5_hash.digest()


def create_md5_zip(zip_path: str, root_folder: str) -> Dict[str, bytes]:
    md5_hashes = {}
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        for folder_name, _, filenames in os.walk(root_folder):
            for filename in filenames:
                file_path = os.path.join(folder_name, filename)
                internal_path = os.path.relpath(file_path, root_folder).replace("\\", "/")
                md5_hashes[internal_path] = hash_md5(file_path)
                zip_file.write(file_path, internal_path, zipfile.ZIP_DEFLATED)
    return md5_hashes
