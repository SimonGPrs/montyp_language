#!/usr/bin/env python3
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
from typing import List, Optional

WORD_OPS = {' plus ': ' + ', ' minus ': ' - ', ' times ': ' * ', ' over ': ' / '}
LITERALS = {' true ': ' True ', ' false ': ' False ', ' null ': ' None '}
COMPARATORS = [ (r'\bis at least\b','>='), (r'\bis at most\b','<='), (r'\bis greater than\b','>'), (r'\bis less than\b','<'), (r'\bequals\b','=='), (r'\bnot equals\b','!=') ]

class MonthyCompiler:
    def __init__(self, indent_unit: str = '    '):
        self.indent_unit = indent_unit
        self.lines: List[str] = []
        self.indent = 0
        self.stack: List[str] = []
    def _emit(self, s: str = '') -> None:
        self.lines.append(self.indent_unit * self.indent + s)
    @staticmethod
    def _strip_comment(line: str) -> str:
        for token in ('#','//'):
            if token in line:
                head, _sep, _tail = line.partition(token)
                if head.count('"') % 2 == 0 and head.count("'") % 2 == 0:
                    return head.rstrip()
        return line
    def _tx_expr(self, expr: str) -> str:
        s = f' {expr} '
        for w, op in WORD_OPS.items(): s = s.replace(w, op)
        for pat, repl in COMPARATORS: s = re.sub(pat, repl, s, flags=re.I)
        for w, lit in LITERALS.items(): s = s.replace(w, lit)
        return s.strip()
    def _say_f(self, inner: str) -> None:
        inner = self._tx_expr(inner)
        inner = inner.replace('\\', r'\\').replace('"', r'\"')
        self._emit(f'print(f"{inner}")')
    def compile(self, source: str, *, filename: Optional[str]=None) -> str:
        self.lines.clear(); self.indent = 0; self.stack.clear()
        for idx, raw in enumerate(source.splitlines(), start=1):
            try:
                self._compile_line(raw)
            except Exception as e:
                where = f"{filename or '<string>'}:{idx}"
                raise type(e)(f"{e} (at {where})")
        if self.stack: raise SyntaxError("Missing 'end' for: " + ' > '.join(self.stack))
        return '\n'.join(self.lines) + '\n'
    def _compile_line(self, raw: str) -> None:
        line = raw.strip()
        if not line: return
        line = self._strip_comment(line)
        if not line: return
        # end
        if re.fullmatch(r'end', line, flags=re.I):
            if not self.stack: raise SyntaxError("'end' with no open block")
            self.stack.pop(); self.indent -= 1; return
        # say: f-string
        m = re.match(r'^say:\s*(.*)$', line, flags=re.I)
        if m: self._say_f(m.group(1)); return
        # say expr
        m = re.match(r'^say\s+(.+)$', line, flags=re.I)
        if m: self._emit(f"print({self._tx_expr(m.group(1))})"); return
        # if ... then ...
        m = re.match(r'^if\s+(.+?)\s+then\s+(.+)$', line, flags=re.I)
        if m:
            self._emit(f"if {self._tx_expr(m.group(1))}:"); self.indent += 1; self.stack.append('if')
            self._compile_line(m.group(2).strip()); self.stack.pop(); self.indent -= 1; return
        # if <cond> [optional ':']
        m = re.match(r'^if\s+(.+?)(?::\s*|\s*)$', line, flags=re.I)
        if m: self._emit(f"if {self._tx_expr(m.group(1))}:"); self.indent += 1; self.stack.append('if'); return
        # repeat N times [do|:]
        m = re.match(r'^repeat\s+(.+?)\s+times(?:\s+do)?(?::\s*|\s*)$', line, flags=re.I)
        if m: self._emit(f"for _ in range(int({self._tx_expr(m.group(1))})):"); self.indent += 1; self.stack.append('repeat'); return
        # def name args [optional ':']
        m = re.match(r'^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*(.*?)(?::\s*|\s*)$', line, flags=re.I)
        if m:
            name = m.group(1); args = [a for a in m.group(2).strip().split() if a]
            self._emit(f"def {name}({', '.join(args)}):"); self.indent += 1; self.stack.append('def'); return
        # return expr
        m = re.match(r'^return\s+(.+)$', line, flags=re.I)
        if m: self._emit(f"return {self._tx_expr(m.group(1))}"); return
        # assignment: name is expr
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s+is\s+(.+)$', line, flags=re.I)
        if m: self._emit(f"{m.group(1)} = {self._tx_expr(m.group(2))}"); return
        # Fallback: raw Python passthrough
        self._emit(raw)

def compile_file(in_path: Path, *, indent_unit: str) -> str:
    src = in_path.read_text(encoding='utf-8')
    compiler = MonthyCompiler(indent_unit=indent_unit)
    py = compiler.compile(src, filename=str(in_path))
    out = in_path.with_suffix('.py')
    out.write_text(py, encoding='utf-8')
    return str(out)

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Monthy v0.2 compiler (indentation-free source → Python)')
    ap.add_argument('file', nargs='?', help='Input .monthy file')
    ap.add_argument('-c', '--code', help='Inline Monthy code string to compile and print Python')
    ap.add_argument('--run', action='store_true', help='Execute the compiled Python after compiling')
    ap.add_argument('-o', '--output', help='Write compiled Python to this path (default: alongside input)')
    ap.add_argument('--indent', type=int, default=4, help='Spaces per indent level (default: 4)')
    ap.add_argument('--tabs', action='store_true', help='Indent with tabs instead of spaces')
    args = ap.parse_args(argv)
    indent_unit = '\t' if args.tabs else (' ' * max(0, args.indent))
    if args.code is not None:
        compiler = MonthyCompiler(indent_unit=indent_unit)
        py = compiler.compile(args.code, filename='<arg -c>')
        sys.stdout.write(py)
        if args.run:
            ns = {}; exec(py, ns, ns)
        return 0
    if not args.file: ap.error('Provide a .monthy file or use -c to compile a string')
    in_path = Path(args.file)
    if not in_path.exists(): ap.error(f'File not found: {in_path}')
    if args.output:
        compiler = MonthyCompiler(indent_unit=indent_unit)
        py = compiler.compile(in_path.read_text(encoding='utf-8'), filename=str(in_path))
        Path(args.output).write_text(py, encoding='utf-8'); py_path = args.output
    else:
        py_path = compile_file(in_path, indent_unit=indent_unit)
    print(py_path)
    if args.run:
        code = Path(py_path).read_text(encoding='utf-8'); ns = {}; exec(code, ns, ns)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
