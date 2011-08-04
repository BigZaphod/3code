#!/usr/bin/env python
"""\
3code Interpreter in Python, revision 1.2
Copyright (c) 2005, Kang Seonghoon (Tokigun).

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import sys

class SyntaxError(Exception):
    def __init__(self, line, message):
        self.line, self.message = line, message
        self.args = (line, message)
    
    def __str__(self):
        if type(self.line) is int:
            return '%s (line %d)' % (self.message, self.line)
        else:
            return '%s (line unknown)' % self.message

################################################################################

class Compiler:
    def tokenize(self, code):
        tokens = []; token = ''
        for char in code:
            if char.isspace() or char in '=[]?':
                if token: tokens.append(token)
                token = ''
                if char in '=[]?': tokens.append(char)
            else:
                token += char
        if token: tokens.append(token)
        return [(token.isdigit() and int or str)(token) for token in tokens]

    def parseline(self, code):
        special = ('', 'i', 'j', 'k', 'x', 'y', 'z')
        prev = ''; result = []
        i = 0
        while i < len(code):
            if code[i] == '[':
                try:
                    begin = i; depth = 1
                    while depth:
                        i += 1
                        if code[i] == '[': depth += 1
                        elif code[i] == ']': depth -= 1
                    result.append((prev,) + tuple(self.parseline(code[begin+1:i])))
                except IndexError:
                    raise SyntaxError, (None, "incomplete function call")
                prev = ''
            elif prev == '=':
                if code[i] in special:
                    result.append('=' + code[i])
                else:
                    raise SyntaxError, (None, "incomplete assignment")
                prev = ''
            elif code[i] == 'then':
                try:
                    begin = i
                    while code[i] != '?' and code[i] != 'else': i += 1
                    block1 = self.parseline(code[begin+1:i])
                    if code[i] == 'else':
                        begin = i
                        while code[i] != '?': i += 1
                        block2 = self.parseline(code[begin+1:i])
                    else:
                        block2 = []
                    result.append((False, block1, block2))
                except IndexError:
                    raise SyntaxError, (None, "incomplete conditional block")
                prev = ''
            elif not (prev in special or type(prev) is int):
                raise SyntaxError, (None, "function should be followed by arguments")
            else:
                if code[i] in special or type(code[i]) is int:
                    result.append(code[i])
                prev = code[i]
            i += 1
        if not (prev in special or type(prev) is int):
            raise SyntaxError, (None, "incomplete statement")
        return result

    def parse(self, string):
        result = []
        lineno = 0
        for line in string.splitlines():
            lineno += 1
            code = self.tokenize(line)
            if len(code) == 0: continue
            if code[0] == 'F':
                if len(code) < 3 or type(code[1]) != str or type(code[2]) != int:
                    raise SyntaxError, (lineno, "invalid function definition")
                if not (0 <= code[2] <= 3):
                    raise SyntaxError, (lineno, "a number of arguments should be 0..3")
                try:
                    rcode = self.parseline(code[3:])
                except SyntaxError, (_, msg):
                    raise SyntaxError, (lineno, msg)
                result.append((True, code[1], code[2], rcode))
            else:
                try:
                    result += self.parseline(code)
                except SyntaxError, (_, msg):
                    raise SyntaxError, (lineno, msg)
        return result
    
    def compile(self, code):
        if not isinstance(code, list):
            code = self.parse(code)

        result = []
        var = lambda x: 'xyzijk'.index(x)
        def travel(tree):
            for i in tree[1:]:
                if type(i) is str: result.append((7, var(i)))
                elif type(i) is int: result.append((6, i))
                else: travel(i)
            result.append((9, tree[0], len(tree)-1))

        for cmd in code:
            if type(cmd) is tuple:
                if cmd[0] == True:
                    result.append((10, cmd[1], cmd[2], self.compile(cmd[3])))
                elif cmd[0] == False:
                    block = self.compile(cmd[1])
                    if len(cmd[2]):
                        block2 = self.compile(cmd[2])
                        result.append((5, len(block) + 1))
                        result += block
                        result.append((4, len(block2)))
                        result += block2
                    else:
                        result.append((5, len(block)))
                        result += block
                elif type(cmd[0]) is str:
                    travel(cmd)
                    result.append((8,))
                else:
                    raise ValueError
            elif type(cmd) is str:
                if len(cmd) == 1:
                    result.append((2, var(cmd[-1])))
                elif len(cmd) == 2 and cmd[0] == '=':
                    result.append((3, var(cmd[-1])))
                else:
                    raise ValueError
            elif type(cmd) is int:
                result.append((1, cmd))
            else:
                raise ValueError
        return result

class VirtualMachine:
    internal_funcs = {
        '>': 2, '<': 2, '=': 2, '>=': 2, '<=': 2,
        '+': 2, '-': 2, '*': 2, '/': 2,
        'nl': 0, 'print': 1, 'println': 1, 'write': 1,
    }

    def __init__(self, cin=sys.stdin, cout=sys.stdout, code=None):
        self.cin, self.cout = cin, cout
        self.reset()
        if code is not None: self.add(code)

    def reset(self):
        self.codes = {}
        self.nargs = self.internal_funcs.copy()
        self.value, self.register = 0, [0] * 6
        self.clear()

    def clear(self, code=None):
        if code is None: code = []
        self.codes[''] = code
        self.func, self.pos = '', 0
        self.callstack, self.argstack = [], []

    def add(self, code):
        self.codes[''] += code
        return self
    __iadd__ = add

    def ifunc(self, name, args):
        if name == '>':
            return int(args[0] > args[1])
        elif name == '<':
            return int(args[0] < args[1])
        elif name == '=':
            return int(args[0] == args[1])
        elif name == '>=':
            return int(args[0] >= args[1])
        elif name == '<=':
            return int(args[0] <= args[1])
        elif name == '+':
            return args[0] + args[1]
        elif name == '-':
            return args[0] - args[1]
        elif name == '*':
            return args[0] * args[1]
        elif name == '/':
            try:
                return args[0] / args[1]
            except ZeroDivisionError:
                raise RuntimeError, "division by zero"
        elif name == 'nl':
            self.cout.write('\n')
        elif name == 'print':
            self.cout.write(str(args[0]))
        elif name == 'println':
            self.cout.write(str(args[0]) + '\n')
        elif name == 'write':
            try:
                self.cout.write(chr(args[0]))
            except ValueError:
                raise RuntimeError, "invalid character number"
        else: # shouldn't be called
            raise RuntimeError, "call for undefined internal function"

    def step(self):
        code = self.codes[self.func]
        while self.pos >= len(code):
            if len(self.callstack) == 0: return False
            self.func, self.pos, self.register[3:] = self.callstack.pop()
            self.argstack.append(self.value)
            code = self.codes[self.func]

        cmd = code[self.pos]
        opcode = cmd[0]
        if opcode == 0: # nop
            pass
        elif opcode == 1: # store <number>
            self.value = cmd[1]
        elif opcode == 2: # get <reg>
            self.value = self.register[cmd[1]]
        elif opcode == 3: # set <reg>
            self.register[cmd[1]] = self.value
        elif opcode == 4: # jmp <offset>
            self.pos += cmd[1]
        elif opcode == 5: # jz <offset>
            if not self.value: self.pos += cmd[1]
        elif opcode == 6: # pushn <number>
            self.argstack.append(cmd[1])
        elif opcode == 7: # push <reg>
            self.argstack.append(self.register[cmd[1]])
        elif opcode == 8: # pop
            try:
                self.value = self.argstack.pop()
            except:
                raise RuntimeError, "argument stack underflow"
        elif opcode == 9: # call <name> <narg>
            if cmd[1] not in self.nargs:
                raise RuntimeError, "function '%s' is not defined." % cmd[1]
            elif self.nargs[cmd[1]] != cmd[2]:
                raise RuntimeError, "function '%s' expected %d argument(s), got %d." % \
                        (cmd[1], self.nargs[cmd[1]], cmd[2])
            else:
                nargs = self.nargs[cmd[1]]
                if nargs > len(self.argstack):
                    raise RuntimeError, "argument stack underflow"
                elif cmd[1] in self.internal_funcs:
                    value = self.ifunc(cmd[1], self.argstack[-nargs:])
                    if value is not None: self.value = value
                    self.argstack[-nargs:] = [self.value]
                else:
                    self.callstack.append((self.func, self.pos+1, self.register[3:]))
                    self.func, self.pos = cmd[1], -1
                    self.register[3:] = self.argstack[-nargs:] + [0] * (3-nargs)
                    del self.argstack[-nargs:]
        elif opcode == 10: # define <name> <narg> <code>
            if cmd[1] in self.nargs: # XXX?
                raise RuntimeError, "function '%s' is already defined." % cmd[1]
            else:
                self.codes[cmd[1]] = cmd[3]
                self.nargs[cmd[1]] = cmd[2]
        else:
            raise RuntimeError, "invalid opcode"

        self.pos += 1
        return True

    def execute(self, code=None):
        self.clear()
        if code is not None: self.add(code)
        while self.step(): pass

################################################################################

def version(apppath):
    print __doc__
    return 0

def help(apppath):
    print __doc__[:__doc__.find('\n\n')]
    print
    print "Usage: %s [options] <filename>" % apppath
    print
    print "--help, -h"
    print "    prints help message."
    print "--version, -V"
    print "    prints version information."
    print "--interactive, -i"
    print "    after executing <filename> (if any), launchs interactive interpreter."
    return 0

def interactive(vm=None):
    if vm is None:
        vm = VirtualMachine()

    compiler = Compiler()
    while 1:
        try:
            line = raw_input('>>> ')
        except (EOFError, KeyboardInterrupt):
            break
        if line.startswith(':'):
            line = line[1:].split()
            cmd = line[0].lower()
            if cmd == 'help':
                print ":help    show this message."
                print ":reset   clear all user-defined functions and states."
                print ":exit    terminate interactive interpreter."
            elif cmd == 'reset':
                vm.reset()
            elif cmd in ('exit', 'quit'):
                break
            else:
                print "Runtime Error: invalid command. type :help for all list of commands."
        else:
            try:
                code = compiler.compile(line)
            except SyntaxError, (lineno, msg):
                print "Syntax Error: %s" % msg
                continue
            try:
                vm.execute(code)
            except RuntimeError, msg:
                print "Runtime Error: %s" % msg
            except KeyboardInterrupt:
                print "Runtime Error: aborted."

def main(argv):
    import getopt

    try:
        opts, args = getopt.getopt(argv[1:], "hVi",
                ['help', 'version', 'interactive'])
    except getopt.GetoptError:
        return help(argv[0])

    is_interactive = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            return help(argv[0])
        if opt in ('-V', '--version'):
            return version(argv[0])
        if opt in ('-i', '--interactive'):
            is_interactive = True
    if not is_interactive and len(args) != 1:
        print __doc__[:__doc__.find('\n\n')]
        return 1

    compiler = Compiler()
    vm = VirtualMachine()
    if len(args) == 1:
        filename = args[0]
        try:
            if filename == '-':
                data = sys.stdin.read()
            else:
                data = file(filename).read()
        except IOError:
            print "Cannot read file: %s" % filename
            return 1
        try:
            code = compiler.compile(data)
        except SyntaxError, (lineno, msg):
            print "Syntax Error: %s (line %d)" % (msg, lineno)
            return 1
        try:
            vm.execute(code)
        except RuntimeError, msg:
            print "Runtime Error: %s" % msg
            return 1
        except KeyboardInterrupt:
            print "Runtime Error: aborted."

    if is_interactive: interactive(vm)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))

