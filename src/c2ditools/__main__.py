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

import argparse
import sys

from c2ditools.archives.why import run_from_args as why_args
from c2ditools.archives.whyjustwhy import run_from_args as whyjustwhy_args
from c2ditools.scene.scene_dec import run_from_args as scene_dec_args
from c2ditools.scene.scene_enc import run_from_args as scene_enc_args

if __name__ == "__main__":
    _ARG_FUNCS = {
        "why": why_args,
        "whyjustwhy": whyjustwhy_args,
        "scene_dec": scene_dec_args,
        "scene_enc": scene_enc_args,
    }

    _argument_parser = argparse.ArgumentParser(
        prog="c2ditools",
        description="Modding tools for Cars 2 and Disney Infinity",
        epilog="https://github.com/TKFRvisionOfficial/Cars2TheVideoGameModding"
    )

    _argument_parser.add_argument("tool", help=f"The tool you want to use.", choices=tuple(_ARG_FUNCS.keys()))

    _args = _argument_parser.parse_args(sys.argv[1:2])
    _ARG_FUNCS[_args.tool](sys.argv[2:])
