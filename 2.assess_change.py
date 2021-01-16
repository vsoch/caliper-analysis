#!/usr/bin/env python3

__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2021, Vanessa Sochat"
__license__ = "MPL 2.0"

import argparse
from glob import glob
from caliper.utils.file import read_json, write_json
from caliper.metrics import MetricsExtractor
from caliper.managers import PypiManager
import sys
import os
import re
import csv


# regular expression to identify raw result files
result_regex = "pypi-tensorflow-(?P<tfversion>.+)-python-cp(?P<pversion>[0-9]+)[.]json"


def get_parser():
    parser = argparse.ArgumentParser(description="Caliper Analysis Runner")
    parser.add_argument(
        "-d",
        "--dir",
        dest="dirname",
        help="path to root caliper directory with results (defaults to .caliper)",
        default=".caliper",
    )
    parser.add_argument(
        "--funcdb",
        dest="funcdb",
        help="path to extracted function database (zip or json)",
        default=".caliper",
    )
    return parser


def write_rows(rows, filename, sep="\t"):
    """Given a list of lists, write to a tab separated file"""
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(
            csvfile, delimiter=sep, quotechar="|", quoting=csv.QUOTE_MINIMAL
        )
        for row in rows:
            writer.writerow(row)
    return filename


def iter_files(dirname):
    """A helper function to iterate over result files (and skip others)"""
    for filename in glob("%s/*" % dirname):
        # Skip over non result files
        if not re.search(result_regex, filename):
            continue
        yield filename


class DependencyVersion:
    """Small helper class to easily derive versions"""

    def __init__(self, filename):
        self.match = re.search(result_regex, filename)

    @property
    def tfversion(self):
        return self.match["tfversion"]

    @property
    def pyversion(self):
        return self.match["pversion"]


def main():
    """main entrypoint for caliper analysis"""
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    dirname = os.path.abspath(args.dirname) if args.dirname else args.dirname
    if not dirname or not os.path.exists(dirname):
        sys.exit("A --dir directory folder with results is required.")

    # Ensure input data directory exists
    datadir = os.path.join(dirname, "data")
    if not os.path.exists(datadir):
        sys.exit("The data directory is missing from the caliper root folder.")

    # Create output directory
    outdir = os.path.join(dirname, "changes")
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    ## Step 1: extract requirements to assses change
    extract_requirements(datadir, outdir)

    outdir = os.path.join(dirname, "sims")
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    # Step 3: load in the function signatures to assess version changes
    extract_function_changes(outdir, args.funcdb)


def information_coefficient(total1, total2, intersect):
    """a simple jacaard (information coefficient) to compare two lists of overlaps/diffs"""
    total = total1 + total2
    return 2.0 * intersect / total


def get_functions(lookup, include_args=False):
    """Given a dictionary with listings of functions and classes, return a
    flattened list of functions, meaning when we encounter a dictionary (class)
    we flatten out it's functions. We assume that there is only up to two
    levels of nesting - from the top we have a class, and then a class can
    have functions. If include args is True, a sorted list of arguments is
    included in the signature.
    """
    # Yes, this code is horrific with ifs and fors, be strong and read it lol
    funcs = []
    for name, items in lookup.items():
        for func, args in items.items():
            # List indicates arguments for a function
            if isinstance(args, list) and include_args:
                funcs.append("%s.%s:%s" % (name, func, "-".join(sorted(args))))
            elif isinstance(args, list) and not include_args:
                funcs.append("%s.%s" % (name, func))
            elif isinstance(args, dict):
                for classfunc, classargs in args.items():
                    if isinstance(classargs, list) and include_args:
                        funcs.append(
                            "%s.%s:%s" % (name, func, "-".join(sorted(classargs)))
                        )
                    elif isinstance(classargs, list) and not include_args:
                        funcs.append("%s.%s.%s" % (name, func, classfunc))

    return funcs


def extract_function_changes(outdir, funcdb):
    """Given a functiondb file (a metric called functiondb served by caliper,
    with an extracted result for tensorflow) iterate over all combinations
    and calculate the change score.
    """
    # We don't need a manager since we aren't extracting from a repository
    extractor = MetricsExtractor("pypi:tensorflow")

    # Read in and load the function database metric
    filename = os.path.abspath(funcdb)
    if not os.path.exists(funcdb):
        sys.exit("Function database file %s does not exist." % funcdb)
    db = extractor.load_metric("functiondb", filename=filename)

    # Level 1 similarity: overall modules
    # Level 2 similarity: functions
    # Level 3 similarity: function arguments too
    sims = {}

    # First just compare functions that exist
    for version1, db1 in db["by-file"].items():
        for version2, db2 in db["by-file"].items():

            # Dont' calculate it twice
            scores = {}
            key = "-".join(sorted([version1, version2]))

            # Keep the user updated
            if key in sims:
                continue

            # Diagonal is perfectly similar
            if version1 == version2:
                scores = {"module_sim": 1, "func_args_sim": 1, "func_sim": 1}
                sims[key] = scores
                continue

            # Level 1: Overall module similarity
            modules1 = set(db1.keys())
            modules2 = set(db2.keys())
            scores["module_sim"] = information_coefficient(
                len(modules1), len(modules2), len(modules1.intersection(modules2))
            )

            # Level 2 and 3: Function and with args similarity
            funcs1 = get_functions(db1, include_args=True)
            funcs2 = get_functions(db2, include_args=True)
            scores["func_args_sim"] = information_coefficient(
                len(set(funcs1)),
                len(set(funcs2)),
                len(set(funcs1).intersection(set(funcs2))),
            )

            # Remove arguments and recalculate
            funcs1 = [x.split(":")[0] for x in funcs1]
            funcs2 = [x.split(":")[0] for x in funcs2]
            scores["func_sim"] = information_coefficient(
                len(set(funcs1)),
                len(set(funcs2)),
                len(set(funcs1).intersection(set(funcs2))),
            )
            sims[key] = scores

    outfile = os.path.join(outdir, "%s-sims.json" % extractor.manager.replace(":", "-"))
    write_json(sims, outfile)
    return outfile


def extract_requirements(datadir, outdir):
    """Given a known list of dependencies for a package, we want to extract all
    requirements (to see change between version) that can then be used to assess
    overall change in a package
    """
    # Keep a lookup of requirements.txt to compare across
    rxments = set()
    requirements = {}

    # Read in input files, organize by python version, tensorflow version
    for filename in iter_files(datadir):

        # Derive the name and versions from the filename (also in inputs:name)
        result = read_json(filename)
        if "requirements.txt" not in result:
            requirements[filename] = {}
            continue

        [
            rxments.add(re.split("(=|@)", x)[0].strip())
            for x in result["requirements.txt"]
        ]

    client = MetricsExtractor()
    for library in rxments:

        try:
            manager = PypiManager(library)
            extractor = MetricsExtractor(manager)
            # extractor.extract_metric("changedlines")
            extractor.extract_metric("totalcounts")
            extractor.save_all(outdir)
            extractor.cleanup(force=True)
        except:
            print("Issue with %s" % library)


if __name__ == "__main__":
    main()
