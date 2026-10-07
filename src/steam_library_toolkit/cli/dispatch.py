"""Dispatch to the same handlers as the supported standalone commands."""
import argparse
from importlib import import_module
import sys

COMMANDS = {'collect': 'collect', 'enrich': 'enrich', 'reclassify': 'reclassify',
            'review': 'review_classification', 'plan': 'collections', 'picker': 'picker',
            'classify': 'classify_table', 'classify-five': 'classify_five', 'node': 'node_runtime'}


def main():
    parser = argparse.ArgumentParser(description='Steam library commands; use COMMAND --help for options')
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.argv = [sys.argv[0] + ' ' + args.command, *args.arguments]
    return import_module('steam_library_toolkit.cli.' + COMMANDS[args.command]).main()
