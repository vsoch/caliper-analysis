#!/usr/bin/env python3

__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2020-2021, Vanessa Sochat"
__license__ = "MPL 2.0"

import argparse
from jinja2 import Template
from caliper.managers import PypiManager
import subprocess
import threading
import yaml
import sys
import os
import json

here = os.path.abspath(os.path.dirname(__file__))

# helper functions


def read_file(filename, readlines=True):
    with open(filename, "r") as filey:
        content = filey.read()
    return content


def write_file(filename, content):
    with open(filename, "w") as filey:
        filey.write(content)


def read_yaml(filename):
    stream = read_file(filename, readlines=False)
    return yaml.load(stream, Loader=yaml.FullLoader)


class CommandRunner(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.error = []
        self.output = []
        self.retval = None

    def reader(self, stream, context):
        """Get output and error lines and save to command runner."""
        # Make sure we save to the correct field
        lines = self.error
        if context == "stdout":
            lines = self.output

        while True:
            s = stream.readline()
            if not s:
                break
            lines.append(s.decode("utf-8"))
        stream.close()

    def run_command(self, cmd, env=None, **kwargs):
        self.reset()

        # If we need to update the environment
        # **IMPORTANT: this will include envars from host. Absolutely cannot
        # be any secrets (they should be defined in the app settings file)
        envars = os.environ.copy()
        if env:
            envars.update(env)

        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=envars, **kwargs
        )

        # Create threads for error and output
        t1 = threading.Thread(target=self.reader, args=(p.stdout, "stdout"))
        t1.start()
        t2 = threading.Thread(target=self.reader, args=(p.stderr, "stderr"))
        t2.start()

        p.wait()
        t1.join()
        t2.join()
        self.retval = p.returncode
        return self.output


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

    config = read_yaml(args.config).get("analysis")

    # Get the Dockerfile, ensure it exists
    dockerfile = config.get("dockerfile", "Dockerfile")
    if not os.path.exists(dockerfile):
        sys.exit("The Dockerfile does not exist.")

    # Read in the template, populate with each deps version
    template = Template(read_file(dockerfile))

    # Currently only supports testing one dependency, and any added args
    dependency = config.get("dependency")
    args = config.get("args", {})
    manager = PypiManager(dependency)

    # Get all version of Python supported for linux (manylinux x86_64)
    all_releases = manager.filter_releases(".*manylinux.*x86_64.*")
    python_versions = manager.get_python_versions()

    # prepare a command runner, check that docker is installe
    runner = CommandRunner()
    runner.run_command(["which", "docker"])
    if runner.retval != 0:
        sys.exit("Docker must be installed to build containers.")

    # make caliper output directory
    outdir = os.path.join(here, ".caliper")
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # Build a container for each version (todo, can we scale this requiring docker?)
    for version, releases in all_releases.items():

        # Don't redo if we already have an output file
        outfile = os.path.join(outdir, "%s-%s.json" % (dependency, version))
        if os.path.exists(outfile):
            continue

        # Create a lookup based on Python version
        lookup = {x["python_version"]: x for x in releases}

        # Store results based on Python versions
        single_result = {x: {} for x in python_versions}
        for python_version in python_versions:
            print("Testing %s" % python_version)

            # We can't do tests if the Python version isn't supported, considered a fail (return value 1)
            if python_version not in lookup:
                single_result[python_version]["build_retval"] = 1
                continue

            # Build a container with the correct Python version and filename
            spec = lookup[python_version]
            container_base = "python:%s" % ".".join(
                [x for x in python_version.lstrip("cp")]
            )
            result = template.render(
                base=container_base,
                filename=spec["url"],
                basename=spec["filename"],
                **args
            )

            # Write and build temporary Dockerfile, and build the container
            write_file("Dockerfile.caliper", result)
            container_name = "%s-container" % dependency
            runner.run_command(
                [
                    "docker",
                    "build",
                    "-f",
                    "Dockerfile.caliper",
                    "-t",
                    container_name,
                    ".",
                ],
                cwd=here,
            )

            # Keep a result for each script
            single_result[python_version]["build_retval"] = runner.retval
            single_result[python_version]["dockerfile"] = result
            if runner.retval != 0:
                continue

            # Get packages installed for each container
            runner.run_command(["docker", "run", container_name, "pip", "freeze"])
            single_result[python_version]["requirements.txt"] = runner.output

            # Test basic import of library
            tests = {}
            runner.run_command(
                ["docker", "run", container_name, "python", "-c", "'import tensorflow'"]
            )
            tests["import tensorflow"] = {
                "error": runner.error,
                "output": runner.output,
                "retval": runner.retval,
            }

            # Run each test
            for script in config.get("tests", []):
                runner.run_command(["docker", "run", container_name, "python", script])
                tests[script] = {
                    "error": runner.error,
                    "output": runner.output,
                    "retval": runner.retval,
                }

            single_result[python_version]["tests"] = tests

        # Save the single result to file
        write_file(outfile, json.dumps(single_result))


if __name__ == "__main__":
    main()
