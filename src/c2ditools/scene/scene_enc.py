#
# Based on the work of the amazing "zzh8829"
# Written by TKFRvision (https://github.com/TKFRvisionOfficial)
# All Rights reserved
#

import os.path

from typing import BinaryIO, List, Sequence, Callable, Iterator, Tuple, Optional
from xml.etree import ElementTree
import struct
import itertools
from .scene_types import SceneHeader, SceneNode
from ..utils import get_str_endianness, chunk_iter, Endianness

_TAG_BLACKLIST = "entry", "root_node"

# ParentElement, Element, count, bytes to write or nothing if it should continue as usual.
ReadBinFileType = Callable[[ElementTree.Element, ElementTree.Element], Tuple[int, Iterator[bytes]] | None]


def create_string_table(input_xml: ElementTree.Element) -> List[str]:
    # making a set first so there aren't double entries
    string_set = set()
    for element in input_xml.iterfind(".//"):
        # xml workaround
        string_set.add(element.tag.strip("__").replace("_____", " "))
    for element in itertools.chain(input_xml.iterfind(".//*[@type='string']"), input_xml.iterfind(".//*[@type='reference_string']")):
        if element.text is None:
            continue  # probably empty string better check that out later
        string_set.add(element.text.strip())
    for element in input_xml.iterfind(".//*[@type='string_list']/entry"):
        string_set.add(element.text)
    for element in input_xml.iterfind(".//*[@type='string_float32_list']"):
        string_set.add(element.text.strip())

    string_table = list(filter(lambda tag: tag not in _TAG_BLACKLIST, string_set))
    return [""] + string_table + [""]


def write_string_table(string_table: List[str], output_stream: BinaryIO) -> int:
    return output_stream.write(b"\x00".join(cur_string.encode("utf-8") for cur_string in string_table))


def convert_xml_to_table(cur_element: ElementTree.Element, string_table: Sequence[str], output_stream: BinaryIO,
                         endianness: Endianness, file_reader: ReadBinFileType, level: int = 1):
    str_endianness = get_str_endianness(endianness)

    def array_to_bytes(element_to_write: ElementTree.Element, count_size: int, conv: Callable[[str], bytes]) -> bytes:
        count_bytes = sum(1 for _ in element_to_write.iterfind("./entry")) \
            .to_bytes(count_size, endianness, signed=False)
        return count_bytes + b"".join(conv(entry.text) for entry in element_to_write.iterfind("./entry"))

    def array_to_bytes_int(element_to_write: ElementTree.Element, count_size: int, element_size: int,
                           signed: bool) -> bytes | Iterator[bytes]:
        file_reader_res = file_reader(cur_element, element_to_write)
        if file_reader_res:
            count, byte_iterator = file_reader_res
            count_bytes = count.to_bytes(count_size, endianness, signed=False)
            return itertools.chain((count_bytes,), byte_iterator)

        return array_to_bytes(element_to_write, count_size,
                              lambda entry: int(entry).to_bytes(element_size, endianness, signed=signed))

    def array_to_bytes_str(element_to_write: ElementTree.Element, count_size: int) -> bytes:
        return array_to_bytes(element_to_write, count_size,
                              lambda entry: string_table.index(entry).to_bytes(2, endianness, signed=False))

    def array_to_bytes_float(element_to_write: ElementTree.Element, count_size: int) -> bytes:
        return array_to_bytes(element_to_write, count_size,
                              lambda entry: struct.pack(str_endianness + "f", float(entry)))

    for element in cur_element.iterfind("./*"):
        if element.tag == "entry":
            continue

        data_format = element.get("type")
        match data_format:
            case None:
                type_id = 0x01
                to_write = b""
            case "reference_string" | "string":
                if data_format == "reference_string":
                    type_id = 0x05
                else:
                    type_id = 0x0B

                if element.text is None:
                    to_write = 0x00.to_bytes(2, endianness, signed=False)
                else:
                    to_write = string_table.index(element.text.strip()).to_bytes(2, endianness, signed=False)
            case "string_list":
                type_id = 0x0A
                to_write = array_to_bytes_str(element, 1)
            case "float_list":
                type_id = 0x12
                to_write = array_to_bytes_float(element, 1)
            case "float":
                type_id = 0x13
                to_write = struct.pack(str_endianness + "f", float(element.text))
            case "int8_list":
                type_id = 0x1A
                to_write = array_to_bytes_int(element, 1, 1, True)
            case "int8":
                type_id = 0x1B
                to_write = int(element.text).to_bytes(1, endianness, signed=True)
            case "uint8_list":
                type_id = 0x23
                to_write = array_to_bytes_int(element, 1, 1, False)
            case "uint16_uint16_list" | "uint16_uint16_list_alt":
                if data_format == "uint16_uint16_list":
                    type_id = 0x4A
                else:
                    type_id = 0x15A
                to_write = array_to_bytes_int(element, 2, 2, False)
            case "uint16_uint8_list" | "uint16_uint8_bin":
                if data_format == "uint16_uint8_list":
                    type_id = 0x5A
                else:
                    type_id = 0x63
                to_write = array_to_bytes_int(element, 2, 1, False)
            case "uint16_list":
                type_id = 0x11A
                to_write = array_to_bytes_int(element, 1, 2, False)
            case "uint16":
                type_id = 0x11B
                to_write = int(element.text).to_bytes(2, endianness, signed=False)
            case "int24_list":
                type_id = 0x21A
                to_write = array_to_bytes_int(element, 1, 3, False)
            case "int24":
                type_id = 0x21B
                to_write = int(element.text).to_bytes(3, endianness, signed=False)
            case "uint32":
                type_id = 0x31B
                to_write = int(element.text).to_bytes(4, endianness, signed=False)
            case "string_float32_list":
                type_id = 0x16
                to_write = string_table.index(element.text.strip()).to_bytes(2, endianness, signed=False)
                to_write += array_to_bytes_float(element, 1)
            case "uint24_uint8_bin":
                type_id = 0xA3
                to_write = array_to_bytes_int(element, 3, 1, False)
            case "float_u16_list":
                type_id = 0x52
                to_write = array_to_bytes_float(element, 2)
            case _:
                raise ValueError(f"Unknown DataFormat {data_format}.")

        # __ is a xml workaround
        output_stream.write(SceneNode(level, type_id,
                                      string_table.index(element.tag.strip("__").replace("_____", " ")
                                                         )).to_bytes(endianness))

        if isinstance(to_write, Iterator):
            for chunk in to_write:
                output_stream.write(chunk)
        else:
            output_stream.write(to_write)

        convert_xml_to_table(element, string_table, output_stream, endianness, file_reader, level + 1)


def convert_xml_scene(in_xml: str, output_stream: BinaryIO, endianness: Endianness, file_reader: ReadBinFileType):
    root_element = ElementTree.fromstring(in_xml)
    # leave space to fill out header later
    output_stream.write(b"\x00" * SceneHeader.get_size())

    string_table = create_string_table(root_element)
    string_table_size = write_string_table(string_table, output_stream)

    # root Node
    output_stream.write(SceneNode(0, 1, 0).to_bytes(endianness))

    convert_xml_to_table(root_element, string_table, output_stream, endianness, file_reader)

    tree_size = output_stream.tell() - string_table_size - SceneHeader.get_size()
    output_stream.seek(0)
    output_stream.write(SceneHeader(string_table_size, tree_size, endianness).to_bytes())


def main(in_file: str, out_file: str, endianness: Endianness, path: Optional[str] = None):
    def read_files(_: ElementTree.Element, element: ElementTree.Element) -> Tuple[int, Iterator[bytes]] | None:
        if filepath := element.get("filepath"):
            assert filepath is not None, f"This xml requires the external file {filepath}. No folder was specified."
            if not os.path.isabs(filepath):
                filepath = os.path.join(path, filepath)
            assert os.path.exists(filepath), f"The file at {filepath} was not found."
            file_size = os.path.getsize(filepath)

            return os.path.getsize(filepath), chunk_iter(open(filepath, "rb"), file_size, close_after=True)
        else:
            return None

    with open(in_file, "r", encoding="utf-8") as xml_file:
        xml_content = xml_file.read()

    with open(out_file, "wb") as scene_file:
        convert_xml_scene(xml_content, scene_file, endianness, read_files)


def run_from_args(args: Sequence[str]):
    import argparse

    arg_parser = argparse.ArgumentParser(
        prog="scene_enc(.py) Written by TKFRvision",
        description="A program to convert xml and texture files generated "
                    "by scene_dec to scene format files (*.oct, *.bent etc.).",
    )

    arg_parser.add_argument("in_file", help="The xml file to convert.")
    arg_parser.add_argument("out_file", help="The resulting scene file.")
    arg_parser.add_argument("-t", dest="texture_folder",
                            help="The texture folder to use. Use if you have a texture folder.")
    arg_parser.add_argument("-c", dest="endianness", action="store_const", const="big", default="little",
                            help="Use this flag to create a scene file for a console. Uses Big Endian.")
    parsed_args = arg_parser.parse_args(args)

    assert os.path.isfile(parsed_args.in_file), "Input file not found."
    assert not os.path.isdir(parsed_args.out_file), "Output file destination is invalid."
    if parsed_args.texture_folder is not None:
        assert os.path.isdir(parsed_args.texture_folder), "Texture folder is invalid."

    main(parsed_args.in_file, parsed_args.out_file, parsed_args.endianness, parsed_args.texture_folder)
