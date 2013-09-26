# vim: set ts=8 sts=2 sw=2 tw=99 et:
import sys
from optparse import OptionParser

class Preparer(object):
  def __init__(self, sourcePath, buildPath):
    self.sourcePath = sourcePath
    self.buildPath = buildPath

    self.options = OptionParser("usage: %prog [options]")
    self.options.add_option("-g", "--gen", type="string", dest="generator", default="ambuild2",
                            help="Build system generator to use. See --list-gen")
    self.options.add_option("--list-gen", action="store_true", dest="list_gen", default=False,
                            help="List available build system generators, then exit.")

  def Configure(self): 
    options, args = self.options.parse_args()

    if options.list_gen:
      print('Available build system generators:')
      print('  {0:24} - AMBuild 2 (default)'.format('ambuild2'))
      print('  {0:24} - Visual Studio project files'.format('vcxproj'))
      sys.exit(0)

    if options.generator == 'ambuild2':
      from frontend.amb2 import gen
      builder = gen.Generator(self.sourcePath, self.buildPath, options, args)
    elif options.generator == 'vcxproj':
      from frontend import vcxproj_gen
      builder = vcxproj_gen.Generator(self.sourcePath, self.buildPath, options, args)
    else:
      sys.stderr.write('Unrecognized build generator: ' + options.generator + '\n')
      sys.exit(1)

    if not builder.Generate():
      sys.stderr.write('Configure failed.\n')
      sys.exit(1)
