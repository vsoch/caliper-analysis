#!/usr/bin/env python3

__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2020-2021, Vanessa Sochat"
__license__ = "MPL 2.0"

import argparse
from caliper.analysis import CaliperAnalyzer
import sys
import os


def get_parser():
    parser = argparse.ArgumentParser(description="Caliper Analysis Runner")
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        help="caliper.yaml with a Dockerfile template, and functions to run",
    )
    return parser


def main():
    """main entrypoint for caliper analysis"""
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    if not args.config or not os.path.exists(args.config):
        sys.exit("A --config yaml file that exists on the filesystem is required.")

    client = CaliperAnalyzer(args.config)
    analyzer = client.get_analyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()
