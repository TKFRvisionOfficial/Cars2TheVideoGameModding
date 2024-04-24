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

from typing import BinaryIO, Literal, Generator

Endianness = Literal["big", "little"]


def chunk_iter(file: BinaryIO, end: int, step: int = 4096, close_after: bool = False) -> Generator[bytes, None, None]:
    while (distance_to_end := end - file.tell()) > 0:
        if distance_to_end >= step:
            yield file.read(step)
        else:
            yield file.read(distance_to_end)
    if close_after:
        file.close()


def get_str_endianness(literal_endianness: Endianness) -> str:
    return ">" if literal_endianness == "big" else "<"
