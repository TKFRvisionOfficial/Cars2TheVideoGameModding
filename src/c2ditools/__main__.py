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
