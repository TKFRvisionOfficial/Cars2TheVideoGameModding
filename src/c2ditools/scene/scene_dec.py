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

#
# Inspired by the work of the amazing "zzh8829"
#

import os
import struct
from typing import BinaryIO, List, Sequence, Callable, Iterator, Optional
from xml.dom import minidom
from xml.etree import ElementTree

from .scene_types import SceneHeader, SceneNode
from ..utils import chunk_iter, get_str_endianness, Endianness

_STRING_ENCODING = "utf-8"  # I know that's stupid

# ParentElement, Element, IteratorForReading, Did I actually read this and do anything?
StoreBinFileType = Callable[[ElementTree.Element, ElementTree.Element, Iterator[bytes]], bool]


def read_string_table(input_stream: BinaryIO, size: int) -> List[str]:
    string_array_bytes = input_stream.read(size)
    return [data_string.decode(_STRING_ENCODING) for data_string in string_array_bytes.split(b"\x00")]


def convert_data_table_to_xml(parent: ElementTree.Element,
                              string_table: Sequence[str],
                              input_stream: BinaryIO,
                              target_pos: int,
                              endianness: Endianness,
                              file_func: StoreBinFileType = None,
                              level: int = 1):
    str_endianness = get_str_endianness(endianness)

    def read_array(element_to_write: ElementTree.Element, count_size: int, element_size: int,
                   conv: Callable[[bytes], str]):
        count = int.from_bytes(input_stream.read(count_size), endianness, signed=False)
        for _ in range(count):
            entry = ElementTree.SubElement(element_to_write, "entry")
            entry.text = conv(input_stream.read(element_size))

    def read_array_int(element_to_write: ElementTree.Element, count_size: int, element_size: int,
                       signed: bool = False):
        # this is so the implementation for file handling is more flexible
        if file_func:
            count = int.from_bytes(input_stream.read(count_size), endianness, signed=False)
            if file_func(parent, element_to_write, chunk_iter(input_stream, input_stream.tell() + count * element_size)):
                return
            else:
                input_stream.seek(-count_size, os.SEEK_CUR)

        read_array(element_to_write, count_size, element_size,
                   lambda in_data: str(int.from_bytes(in_data, endianness, signed=signed)))

    def read_array_str(element_to_write: ElementTree.Element, count_size: int):
        read_array(element_to_write, count_size, 2,
                   lambda in_data: string_table[int.from_bytes(in_data, endianness, signed=False)])

    def read_array_float(element_to_write: ElementTree.Element, count_size: int):
        read_array(element_to_write, count_size, 4,
                   lambda in_data: str(struct.unpack(str_endianness + "f", in_data)[0]))

    while input_stream.tell() < target_pos:
        # read flag
        scene_node = SceneNode.from_bytes(input_stream.read(4), endianness)

        # check if we have to go up a level
        if scene_node.level < level:
            # restoring offset from before flag and name read
            input_stream.seek(-SceneNode.get_size(), os.SEEK_CUR)
            return

        # looking up tag
        name = string_table[scene_node.str_index]
        if name[0].isdigit():  # stupid workaround because of xml limitation
            name = "__" + name
        name = name.replace(" ", "_____")  # even more stupid workaround because of space

        # creating our element
        own_element = ElementTree.SubElement(parent, name)

        # checking the data format
        match scene_node.type_int:
            case 0x01:  # empty
                pass
            case 0x05 | 0x0B:  # String from table; id (uint16)  | 0x3a7 timestamp
                if scene_node.type_int == 0x05:
                    own_element.set("type", "reference_string")
                else:
                    own_element.set("type", "string")
                data_string = string_table[int.from_bytes(input_stream.read(2), endianness, signed=False)]
                own_element.text = data_string
                # own_element.tag = data_string
            case 0x0A:  # list of strings from table; count (uint8), id (uint16)
                own_element.set("type", "string_list")
                read_array_str(own_element, 1)
            case 0x0F:  # string with string (I think 😂)
                own_element.set("type", "string_string")
                own_element.text = string_table[int.from_bytes(input_stream.read(2), endianness, signed=False)]
                main_data = string_table[int.from_bytes(input_stream.read(2), endianness, signed=False)]
                own_element.set("content", main_data)
            case 0x1F:  # int8 with string
                own_element.set("type", "uint8_string")
                own_element.text = string_table[int.from_bytes(input_stream.read(2), endianness, signed=False)]
                main_data = int.from_bytes(input_stream.read(1), endianness, signed=False)
                own_element.set("content", str(main_data))
            case 0x4A:  # list of string from table; count(uint16), id (uint16)
                own_element.set("type", "uint16_string_list")
                read_array_str(own_element, 2)
            case 0x12:  # list of float; count (uint8), float
                own_element.set("type", "float_list")
                read_array_float(own_element, 1)
            case 0x13:  # float
                own_element.set("type", "float")
                own_element.text = str(struct.unpack(str_endianness + "f", input_stream.read(4))[0])
            case 0x1A:  # list of int8; count (uint8)
                own_element.set("type", "int8_list")
                read_array_int(own_element, 1, 1, True)
            case 0x1B:  # int8
                own_element.set("type", "int8")
                own_element.text = str(int.from_bytes(input_stream.read(1), endianness, signed=True))
            case 0x23:  # list of uint8; count (uint8)
                own_element.set("type", "uint8_list")
                read_array_int(own_element, 1, 1, False)
            case 0x15A:  # list of (uint16); count (uint16)
                own_element.set("type", "uint16_uint16_list")
                read_array_int(own_element, 2, 2, False)
            case 0x5A | 0x63:  # list of uint8; count (uint16)
                if scene_node.type_int == 0x5A:
                    own_element.set("type", "uint16_uint8_list")
                else:
                    own_element.set("type", "uint16_uint8_bin")
                read_array_int(own_element, 2, 1, False)
            case 0x11A:  # list of uint16; count (uint8)
                own_element.set("type", "uint16_list")
                read_array_int(own_element, 1, 2, False)
            case 0x11B:  # uint16
                own_element.set("type", "uint16")
                own_element.text = str(int.from_bytes(input_stream.read(2), endianness, signed=False))
            case 0x21A:  # lint24? or uint24?; count (uint8)
                own_element.set("type", "int24_list")
                read_array_int(own_element, 1, 3, True)
            case 0x21B:  # int24? or uint24?
                own_element.set("type", "int24")
                own_element.text = str(int.from_bytes(input_stream.read(3), endianness, signed=False))
            case 0x31B:  # uint32
                own_element.set("type", "uint32")
                own_element.text = str(int.from_bytes(input_stream.read(4), endianness, signed=False))
            case 0x16:  # string from table (uint16); count (uint8); table of float32 (maybe uint32 idk)
                own_element.set("type", "string_float32_list")
                own_element.text = string_table[int.from_bytes(input_stream.read(2), endianness, signed=False)]
                read_array_float(own_element, 1)
            case 0xA3:  # list (uint8); count uint24
                own_element.set("type", "uint24_uint8_bin")
                read_array_int(own_element, 3, 1, False)
            case 0x52:  # list (float); count u16
                own_element.set("type", "float_u16_list")
                read_array_float(own_element, 2)
            case _:
                raise ValueError(f"Unknown DataFormat {hex(scene_node.type_int)} at {hex(input_stream.tell())}")

        # check if we already reached the end of the file
        # this is a botch to prevent an infinite loop
        if input_stream.tell() >= target_pos:
            return

        # reading next flag to check if we have to go down a level
        scene_node = SceneNode.from_bytes(input_stream.read(scene_node.get_size()), endianness)
        input_stream.seek(-SceneNode.get_size(), os.SEEK_CUR)

        if scene_node.level > level:
            convert_data_table_to_xml(own_element, string_table, input_stream, target_pos, endianness, file_func,
                                      scene_node.level)


def convert_scene_xml(input_stream: BinaryIO, store_bin_file: StoreBinFileType = None):
    header = SceneHeader.from_file(input_stream)
    string_table = read_string_table(input_stream, header.string_table_size)

    # root node 1, 0
    input_stream.read(4)
    root = ElementTree.Element("root_node")

    # get file size
    start_pos = input_stream.tell()
    input_stream.seek(0, os.SEEK_END)
    end_pos = input_stream.tell()

    # reading and converting the data
    input_stream.seek(start_pos)
    try:
        convert_data_table_to_xml(root, string_table, input_stream, end_pos, header.endianness, store_bin_file)
    except ValueError as value_error:
        print(value_error)
    return root


def main(file_in: str, file_out: str, bin_folder: Optional[str] = None):
    def store_bin_file(parent_element: ElementTree.Element,
                       element: ElementTree.Element,
                       dds_data: Iterator[bytes]) -> bool:
        if bin_folder and parent_element.tag == "Texture" and element.tag == "Data":
            filename = f"{parent_element.find('./Name').text}.dds"
            with open(os.path.join(bin_folder, filename), "wb") as bin_file:
                for bin_chunk in dds_data:
                    bin_file.write(bin_chunk)
            element.set("filepath", filename)
            return True
        return False

    if bin_folder and not os.path.isdir(bin_folder):
        os.mkdir(bin_folder)

    with open(file_in, "rb") as scene_file:
        result_xml = convert_scene_xml(scene_file, store_bin_file)
        print(scene_file.tell())

    with open(file_out, "w", encoding="utf-8") as xml_file:
        xml_file.write(minidom.parseString(ElementTree.tostring(result_xml)).toprettyxml(indent="   "))


def run_from_args(args: Sequence[str]):
    import argparse

    arg_parser = argparse.ArgumentParser(
        prog="scene_dec(.py) Written by TKFRvision",
        description="A program to convert scene format files (.oct, .bent etc.) to xml and extract the textures."
    )

    arg_parser.add_argument("in_file", help="The scene file to convert.")
    arg_parser.add_argument("out_file", help="The resulting xml file.")
    arg_parser.add_argument("-t", dest="texture_folder", help="A folder to store the textures in.")
    parsed_args = arg_parser.parse_args(args)

    assert os.path.isfile(parsed_args.in_file), "Input file not found."
    assert not os.path.isdir(parsed_args.out_file), "Output file destination is invalid."
    if parsed_args.texture_folder:
        assert not os.path.isfile(parsed_args.texture_folder), "Texture folder is invalid."

    main(parsed_args.in_file, parsed_args.out_file, parsed_args.texture_folder)
