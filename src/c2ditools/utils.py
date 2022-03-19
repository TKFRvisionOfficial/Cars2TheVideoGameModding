from typing import BinaryIO, Literal


def chunk_iter(file: BinaryIO, end: int, step: int = 4096, close_after: bool = False):
    while (distance_to_end := end - file.tell()) > 0:
        if distance_to_end >= step:
            yield file.read(step)
        else:
            yield file.read(distance_to_end)
    if close_after:
        file.close()


def get_str_endianness(literal_endianness: Literal["big", "little"]) -> str:
    return ">" if literal_endianness == "big" else "<"


Endianness = Literal["big", "little"]
