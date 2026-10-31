"""Command line entry point: `fusion-agent [options] [command]`."""
import argparse
import sys

from fusion_agent import __version__

DESCRIPTION = ("A local model (Ollama) designs and edits parts in Autodesk Fusion through Fusion's MCP server. "
               "Run without a command to start the interactive session.")

COMMANDS_HELP = """commands:
  (none)        start the interactive session
  doctor        run the startup checks and print a hint for each problem
  setup-model   install the tuned model gemma4-12b:q8_0 (asks before downloading)
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fusion-agent",
        description=DESCRIPTION,
        epilog=COMMANDS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", choices=["doctor", "setup-model"], metavar="command",
                        help="doctor or setup-model (see below)")
    parser.add_argument("--model", help="Ollama model to use (default: the last one chosen, else gemma4-12b:q8_0)")
    parser.add_argument("--think", action="store_true",
                        help="slow, more accurate mode: the model thinks before answering")
    parser.add_argument("--verbose", action="store_true", help="show the scripts the model runs in Fusion")
    parser.add_argument("--no-screenshots", action="store_true",
                        help="do not take a screenshot after each change of the design")
    parser.add_argument("--new", action="store_true", help="start in a new empty design")
    parser.add_argument("--selftest", action="store_true",
                        help="run three quick tasks in a new design and report pass/fail")
    parser.add_argument("--version", action="version", version="fusion-agent " + __version__)
    return parser


def make_output_safe():
    """Never crash on a character the output encoding cannot show (pipes on Windows use the ANSI code page)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    make_output_safe()
    args = build_parser().parse_args(argv)
    print("fusion-agent %s: not implemented yet (%s)." % (__version__, args.command or "session"))
    return 0
