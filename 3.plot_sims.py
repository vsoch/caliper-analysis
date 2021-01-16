#!/usr/bin/env python3

__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2021, Vanessa Sochat"
__license__ = "MPL 2.0"

import argparse
from caliper.utils.file import read_json

import sys
import matplotlib.pyplot as plt
import os
import pandas


def get_parser():
    parser = argparse.ArgumentParser(description="Caliper Analysis Runner")
    parser.add_argument(
        "--filename",
        dest="filename",
        help="path to the file with similarity scores to plot.",
    )
    parser.add_argument(
        "--outdir", dest="outdir", help="path to output directory.", default=".caliper"
    )
    return parser


def main():
    """main entrypoint for caliper analysis"""
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    filename = os.path.abspath(args.filename) if args.filename else None
    if not filename or (filename and not os.path.exists(filename)):
        sys.exit("A --filename with similarity scores is required.")

    # Prepare output directory
    if not args.outdir or not os.path.exists(args.outdir):
        sys.exit("The output directory %s does not exist" % args.outdir)

    sims = read_json(filename)

    # First derive list of labels for rows and columns
    labels = set()
    for key in sims:
        label1, label2 = key.split(
            "-"
        )  # important, other libraries should use .. in case - is part of the version
        labels.add(label1)
        labels.add(label1)

    labels = sorted(list(labels))

    # Next create a data frame for each
    dfs = {
        x: pandas.DataFrame(index=labels, columns=labels)
        for x in sims[list(sims.keys())[0]].keys()
    }
    for pair, values in sims.items():
        label1, label2 = pair.split("-")
        for key, value in values.items():
            dfs[key].loc[label1, label2] = value
            dfs[key].loc[label2, label1] = value

    # Create output directory
    outdir = os.path.join(args.outdir, "plots")
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    # Finally, prepare plots!
    for name, df in dfs.items():
        fig, ax = plt.subplots(figsize=(20, 20))
        cax = ax.matshow(df.to_numpy(dtype=float), interpolation="nearest")
        ax.grid(True)
        plt.title("Tensorflow Version Similarity: %s" % name)
        plt.xticks(range(len(labels)), labels, rotation=90)
        plt.yticks(range(len(labels)), labels)
        fig.colorbar(
            cax,
            ticks=[
                0,
                0.1,
                0.2,
                0.3,
                0.4,
                0.5,
                0.6,
                0.7,
                0.75,
                0.8,
                0.85,
                0.90,
                0.95,
                1,
            ],
        )
        # plt.show()
        outfile = os.path.join(outdir, "pypi-tensorflow-%s-plot.svg" % name)
        print("Saving %s" % outfile)
        plt.savefig(outfile, dpi=300)


if __name__ == "__main__":
    main()
