# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function
import os, sys
from optparse import OptionParser
from ambuild2 import util
from ambuild2.context import Context

DEFAULT_API = '2.2'
CURRENT_API = '2.2'

SampleScript = """# vim: set sts=4 ts=8 sw=4 tw=99 et ft=python:
builder.cxx = builder.DetectCxx()
if builder.cxx.like('gcc'):
    builder.cxx.cflags += [
        '-Wall',
        '-Werror'
    ]

program = builder.cxx.Program('sample')
program.sources += [
    'main.cpp',
]
builder.Add(program)
"""

SampleConfigure = """# vim: set sts=4 ts=8 sw=4 tw=99 et:
API_VERSION = '{DEFAULT_API}'

import sys
try:
    from ambuild2 import run
    if not run.HasAPI(API_VERSION):
        raise Exception()
except:
    sys.stderr.write('AMBuild {{0}} must be installed to build this project.\\n'.format(API_VERSION))
    sys.stderr.write('http://www.alliedmods.net/ambuild\\n')
    sys.exit(1)

builder = run.BuildParser(sourcePath = sys.path[0], api=API_VERSION)
builder.Configure()
""".format(DEFAULT_API = DEFAULT_API)

def BuildOptions():
    parser = OptionParser("usage: %prog [options] [path]")
    parser.add_option("--no-color",
                      dest = "no_color",
                      action = "store_true",
                      default = False,
                      help = "Disable console colors.")
    parser.add_option("--show-graph",
                      dest = "show_graph",
                      action = "store_true",
                      default = False,
                      help = "Show the dependency graph and then exit.")
    parser.add_option("--show-changed",
                      dest = "show_changed",
                      action = "store_true",
                      default = False,
                      help = "Show the list of dirty nodes and then exit.")
    parser.add_option("--show-damage",
                      dest = "show_damage",
                      action = "store_true",
                      default = False,
                      help = "Show the computed change graph and then exit.")
    parser.add_option("--show-commands",
                      dest = "show_commands",
                      action = "store_true",
                      default = False,
                      help = "Show the computed command graph and then exit.")
    parser.add_option("--show-steps",
                      dest = "show_steps",
                      action = "store_true",
                      default = False,
                      help = "Show the computed build steps and then exit.")
    parser.add_option(
        "-j",
        "--jobs",
        dest = "jobs",
        type = "int",
        default = 0,
        help = "Number of worker processes. Minimum number is 1; default is #cores * 1.25.")
    parser.add_option('--refactor',
                      dest = "refactor",
                      action = "store_true",
                      default = False,
                      help = "Abort the build if the dependency graph would change.")
    parser.add_option('--new-project',
                      dest = "new_project",
                      action = "store_true",
                      default = False,
                      help = "Export a sample AMBuildScript in the current folder.")

    options, argv = parser.parse_args()

    if len(argv) > 1:
        parser.error("expected path, found extra arguments")

    if options.new_project:
        if os.path.exists('AMBuildScript'):
            sys.stderr.write('An AMBuildScript file already exists here; aborting.\n')
            sys.exit(1)
        if os.path.exists('configure.py'):
            sys.stderr.write('A configure.py file already exists here; aborting.\n')
            sys.exit(1)

        with open('AMBuildScript', 'w') as fp:
            fp.write(SampleScript)
        with open('configure.py', 'w') as fp:
            fp.write(SampleConfigure)

        sys.stdout.write('Sample AMBuildScript and configure.py scripts generated.\n')
        sys.exit(0)

    return options, argv

def Build(buildPath, options, argv):
    with util.FolderChanger(buildPath):
        with Context(buildPath, options, argv) as cx:
            return cx.Build()

def CompatBuild(buildPath):
    options, argv = BuildOptions()
    return Build(buildPath, options, argv)

def PrepareBuild(sourcePath, buildPath = None):
    return BuildParser(sourcePath, '2.0', buildPath)

class ApiVersionNotFoundException(Exception):
    def __init__(self, *args, **kwargs):
        super(ApiVersionNotFoundException, self).__init__(*args, **kwargs)

def PreparerForAPI(api):
    if api == '2.0':
        from ambuild2.frontend.v2_0.prep import Preparer
    elif api == '2.1' or api.startswith('2.1.'):
        from ambuild2.frontend.v2_1 import Preparer
    elif api == '2.2' or api.startswith('2.2.'):
        from ambuild2.frontend.v2_2.prep import Preparer
    else:
        message = "AMBuild {} not found; {} is installed. Do you need to upgrade?\n".format(
            api, CURRENT_API)
        raise ApiVersionNotFoundException(message)

    return Preparer

def HasAPI(api):
    try:
        if PreparerForAPI(api) is not None:
            return True
    except:
        pass
    return False

def BuildParser(sourcePath, api, buildPath = None):
    if buildPath == None:
        buildPath = os.path.abspath(os.getcwd())

    Preparer = PreparerForAPI(api)
    return Preparer(sourcePath = sourcePath, buildPath = buildPath)

def cli_run():
    options, argv = BuildOptions()

    if not len(argv):
        folder = '.'
    else:
        folder = argv[0]
        if not os.path.exists(folder):
            sys.stderr.write('Error: path does not exist: {0}\n'.format(folder))
            sys.exit(1)

    cache_path = os.path.join(folder, '.ambuild2', 'graph')
    if not os.path.exists(cache_path):
        sys.stderr.write('Error: folder was not configured for AMBuild.\n')
        sys.exit(1)

    if not Build(os.path.abspath(folder), options, argv):
        sys.exit(1)
