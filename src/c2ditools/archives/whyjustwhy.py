import itertools
import os
import shutil
import tempfile
from Crypto.Cipher import AES

from .archive_utils import ZipEndLocator, ZipDirEntry, ZipFileRecord, EncFileHeader, EncFileEntry, create_md5_zip, ENC_KEY
from ..utils import chunk_iter
from typing import BinaryIO, Sequence

try:
    import mmh3 as mmh3
except ImportError:
    import pymmh3 as mmh3


def update_and_write_dir_entries(file_from: BinaryIO, file_to: BinaryIO, from_loc: int, to_loc: int,
                                 md5_hashes: dict, to_add: int):
    cipher = AES.new(ENC_KEY, AES.MODE_CTR, nonce=b"")
    # set counter of cipher to 22 because that's what the counter has to be set to for some reason
    cipher.encrypt(b"\x01" * 22)
    file_from.seek(from_loc)
    while file_from.tell() < to_loc:
        zip_dir_entry = ZipDirEntry.from_file(file_from)
        zip_dir_entry.header_offset += to_add
        zip_dir_entry.extra_field = md5_hashes[zip_dir_entry.file_name]
        zip_dir_entry.external_attributes = 0  # overwriting them because orig files doesn't have them
        file_to.write(cipher.encrypt(zip_dir_entry.to_bytes()))
        # file_to.write(zip_dir_entry.to_bytes())


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

            # generate encrypted file entries
            size_enc_header = zip_end_locator.total_entries * EncFileEntry.get_size() + EncFileHeader.get_size_without_str()

            # generating enc file entries
            zip_dir_entries = []
            enc_file_entries = []
            tmp_file.seek(zip_end_locator.directory_offset)
            while tmp_file.tell() < zip_end_locator_offset:
                zip_dir_entry = ZipDirEntry.from_file(tmp_file)
                zip_dir_entries.append(zip_dir_entry)
                # thanks jiro 😉
                enc_file_entry = EncFileEntry(mmh3.hash(zip_dir_entry.file_name, signed=False), zip_dir_entry.header_offset + size_enc_header)
                enc_file_entries.append(enc_file_entry)

            # writing enc file header
            final_file.write(EncFileHeader(enc_file_entries).to_bytes_enc())
            # final_file.write(EncFileHeader(enc_file_entries).to_bytes())

            # reading and writing zip file records
            tmp_file.seek(0)
            for next_offset in sorted(itertools.chain((enc_file_entry.header_offset for enc_file_entry in zip_dir_entries[1:]), (zip_end_locator.directory_offset,))):
                cipher = AES.new(ENC_KEY, AES.MODE_CTR, nonce=b"")
                zip_file_record = ZipFileRecord.from_file(tmp_file)
                final_file.write(cipher.encrypt(zip_file_record.to_bytes()))
                # only first 0x200 bytes are encrypted while dct files are not encrypted at all
                if not zip_file_record.name.endswith("dct"):
                    for chunk in chunk_iter(tmp_file, min(next_offset, 0x200 + tmp_file.tell())):
                        final_file.write(cipher.encrypt(chunk))
                for chunk in chunk_iter(tmp_file, next_offset):
                    final_file.write(chunk)

            # reading and writing dir entries
            update_and_write_dir_entries(tmp_file, final_file, zip_end_locator.directory_offset, zip_end_locator_offset,
                                         md5_hashes, size_enc_header)

            # write end locator
            cipher = AES.new(ENC_KEY, AES.MODE_CTR, nonce=b"")
            size_of_md5_fields = zip_end_locator.total_entries * 23  # md5 bytes + header
            zip_end_locator.directory_offset += size_enc_header
            zip_end_locator.directory_size += size_of_md5_fields
            final_file.write(cipher.encrypt(zip_end_locator.to_bytes()))
            # final_file.write(zip_end_locator.to_bytes())

    finally:
        shutil.rmtree(tmp_dir)


def run_from_args(args: Sequence[str]):
    import argparse

    _arg_parser = argparse.ArgumentParser(
        prog="whyjustwhy(.py) did we bother. Written by TKFRvision",
        description="A program to pack encrypted zips for Disney Infinity 3.0",
    )
    _arg_parser.add_argument("in_folder", help="The files of this folder will get packed.")
    _arg_parser.add_argument("out_file", help="The destination of the file that will be generated.")
    _args = _arg_parser.parse_args(args)

    assert os.path.isdir(_args.in_folder), "folder is not valid"
    assert not os.path.isdir(_args.out_file), "file destination is not valid"

    main(_args.in_folder, _args.out_file)
