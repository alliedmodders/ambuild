# vim: set ts=2 sw=2 tw=99 et:
import datetime

def main():
    with open('sample.h', 'w') as fp:
        fp.write("const char* DATE = {0};\n".format(datetime.datetime.now()))

if __name__ == '__main__':
    main()
