# vim: set sts=2 ts=8 sw=2 tw=99 et:
import sys

with open(sys.argv[1], 'w') as fp:
    fp.write("""
#ifndef HELLO_STRING
# define HELLO_STRING "HELLO!"
#endif
""")
