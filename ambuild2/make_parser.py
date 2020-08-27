# vim: set sts=4 ts=8 sw=4 tw=99 et:

def LineHasContinuation(line):
    num_escapes = 0

    pos = len(line) - 1
    while pos >= 0:
        if line[pos] != '\\':
            break
        num_escapes += 1
        pos -= 1

    return num_escapes % 2 == 1

def Preprocess(lines):
    chars = ''

    ignoring = False
    for line in lines:
        if line.endswith('\n'):
            line = line[:len(line) - 1]
        has_continuation = LineHasContinuation(line)
        if has_continuation:
            if ignoring:
                continue
            if line.startswith('#'):
                ignoring = True
                continue
            chars += line[:len(line) - 1]
        else:
            ignoring = False
            if line.startswith('#'):
                continue
            chars += line
    return chars

class Parser(object):
    def __init__(self, fp):
        self.chars_ = Preprocess(fp.readlines())
        self.pos_ = 0

    def parse(self):
        tok = self.lex(':')
        if tok is None or self.peek() != ':':
            raise Exception('No Makefile dependency rules found')
        self.pos_ += 1

        items = []
        while True:
            tok = self.lex()
            if tok == '\n' or tok == '\r' or tok is None:
                break
            if tok.isspace():
                continue
            items.append(tok)
        return items

    def lex(self, stop_token = None):
        token = self.peek()
        if token is None:
            return None
        self.pos_ += 1

        if token.isspace():
            return token

        while True:
            c = self.peek()
            if c is None or c == stop_token or c.isspace():
                break
            self.pos_ += 1
            if c == '\\':
                next_char = self.peek()
                if next_char is None:
                    token += '\\'
                    continue
                token += next_char
                self.pos_ += 1
            else:
                token += c

        return token

    def skip_newline(self, c):
        if c == '\r':
            self.pos_ += 1
            if self.peek() == '\n':
                self.pos_ += 1
            return True
        if self.peek() == '\n':
            self.pos_ += 1
            return True
        return False

    def peek(self):
        if self.pos_ >= len(self.chars_):
            return None
        return self.chars_[self.pos_]

def ParseDependencyFile(filename, fp):
    p = Parser(fp)
    return p.parse()
