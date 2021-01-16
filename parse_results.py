#!/usr/bin/env python3

__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2021, Vanessa Sochat"
__license__ = "MPL 2.0"

import argparse
from glob import glob
from caliper.utils.file import read_json, write_json
from caliper.metrics import MetricsExtractor
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
        help="path to directory with caliper results (defaults to .caliper)",
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

    # Create output directory
    outdir = os.path.join(dirname, "compiled")
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    ## Step 1: extract requirements to assses change
    extract_requirements(dirname, outdir)

    # parse_requirements(dirname, outdir)

    # Step 2: build fail/success, put all results into one file
    # parse_tests(dirname, outdir)

    # Step 3: create separated tests (breaking into python version)
    # parse_versioned_tests(dirname, outdir)


def extract_requirements(dirname, outdir):
    """Given a known list of dependencies for a package, we want to extract all
    requirements (to see change between version) that can then be used to assess
    overall change in a package
    """
    client = MetricsExtractor()
    for name, metric in client.metrics.items():
        if not args.query:
            print("%20s: %s" % (name, metric))
        elif args.query and re.search(args.query, name):
            print("%20s: %s" % (name, metric))


def parse_versioned_tests(dirname, outdir):
    """Instead of a single results file, we want to create a tsv export to
    show
    """
    pass


def parse_tests(dirname, outdir):
    """Assemble all tests results into one large data structure. This will
    be too large to load into the browser at once, but should be okay for Flask.
    """
    results = {}

    # Read in input files, organize by python version, tensorflow version
    for filename in iter_files(dirname):

        # Create object to parse versions
        dep = DependencyVersion(filename)

        # Derive the name and versions from the filename (also in inputs:name)
        result = read_json(filename)
        basename = os.path.splitext(os.path.basename(filename))[0]
        if "tests" not in result:
            result["tests"] = {"build": {"retval": result["build_retval"]}}
        results[basename] = {
            "tests": result["tests"],
            "python": dep.pyversion,
            "tensorflow": dep.tfversion,
        }

    outfile = os.path.join(outdir, "tests.json")
    write_json(results, outfile)
    return outfile


def parse_requirements(dirname, outdir):
    """Given an output directory with json files, parse the requirements.txt
    into a data structure and save into a compiler folder
    """
    # Keep a lookup of requirements.txt to compare across
    rxments = set()
    requirements = {}

    # Read in input files, organize by python version, tensorflow version
    for filename in iter_files(dirname):

        # Derive the name and versions from the filename (also in inputs:name)
        result = read_json(filename)
        if "requirements.txt" not in result:
            requirements[filename] = {}
            continue

        [
            rxments.add(re.split("(=|@)", x)[0].strip())
            for x in result["requirements.txt"]
        ]

    # Now create a flattened dict frame with versions, and a lookup
    requirements = {}
    for filename in iter_files(dirname):

        versions = dict.fromkeys(rxments, None)
        dep = DependencyVersion(filename)
        basename = os.path.splitext(os.path.basename(filename))[0]

        # **Important** this is specific to tensorflow
        for x in result["requirements.txt"]:
            if "file://" in x:
                versions["tensorflow"] = dep.tfversion
            else:
                version = re.split("(==|@|<=|>=)", x)[-1].strip()
                library = re.split("(==|@|<=|>=)", x)[0].strip()
                versions[library] = version

        requirements[basename] = versions

    # Finally, create a data frame (of lists)
    df = [["name", "x", "y", "value", "tensorflow", "python"]]
    for ycoord, requirement in enumerate(rxments):
        for xcoord, filename in enumerate(iter_files(dirname)):

            # Create object to parse versions
            dep = DependencyVersion(filename)
            basename = os.path.splitext(os.path.basename(filename))[0]
            df.append(
                [
                    basename,
                    xcoord,
                    ycoord,
                    requirements[basename][requirement],
                    dep.tfversion,
                    dep.pyversion,
                ]
            )

    # Save versions and matrix to file
    outfile = os.path.join(outdir, "requirements.txt.json")
    write_json(requirements, outfile)
    outfile = os.path.join(outdir, "requirements.txt.tsv")
    write_rows(df, outfile, sep="\t")
    return outfile


if __name__ == "__main__":
    main()
