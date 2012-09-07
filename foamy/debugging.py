class Dumper(object):
    def __init__(self, stream):
        self.indent_level = 0
        self.stream = stream

    def write(self, line):
        line = ("  " * self.indent_level) + line
        self.stream.write(line + "\n")

    def enter(self, name = None):
        if name:
            self.write(name)
        self.indent_level += 1

    def exit(self):
        self.indent_level -= 1

    def __enter__(self):
        self.enter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exit()