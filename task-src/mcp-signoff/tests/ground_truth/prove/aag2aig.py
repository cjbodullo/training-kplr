"""convert ascii aiger with arbitrary variable order into canonical binary aiger."""
import sys

def convert(src, dst):
    L = open(src).read().split('\n')
    _, M, I, Lc, O, A = L[0].split(); I, Lc, O, A = int(I), int(Lc), int(O), int(A)
    p = 1
    ins = [int(L[p + i]) for i in range(I)]; p += I
    lat = [list(map(int, L[p + i].split())) for i in range(Lc)]; p += Lc
    outs = [int(L[p + i]) for i in range(O)]; p += O
    ands = [tuple(map(int, L[p + i].split())) for i in range(A)]
    vm = {0: 0}
    n = 0
    for l in ins:
        n += 1; vm[l >> 1] = n
    for x in lat:
        n += 1; vm[x[0] >> 1] = n
    # topological order of ands
    defs = {a[0] >> 1: a for a in ands}
    order, seen = [], set()
    for a in ands:
        stack = [(a[0] >> 1, 0)]
        while stack:
            v, st = stack.pop()
            if v in seen or v not in defs:
                continue
            if st == 0:
                stack.append((v, 1))
                for r in defs[v][1:]:
                    if (r >> 1) in defs and (r >> 1) not in seen:
                        stack.append((r >> 1, 0))
            else:
                seen.add(v); order.append(v)
    for v in order:
        n += 1; vm[v] = n
    T = lambda l: vm[l >> 1] * 2 + (l & 1)
    out = bytearray()
    out += f"aig {n} {I} {Lc} {O} {len(order)}\n".encode()
    for x in lat:
        nxt = T(x[1])
        if len(x) > 2 and x[2] != 0:
            init = 1 if x[2] == 1 else T(x[0])
            out += f"{nxt} {init}\n".encode()
        else:
            out += f"{nxt}\n".encode()
    for o in outs:
        out += f"{T(o)}\n".encode()
    def enc(x):
        b = bytearray()
        while x & ~0x7f:
            b.append((x & 0x7f) | 0x80); x >>= 7
        b.append(x); return b
    for v in order:
        a = defs[v]
        lhs = vm[v] * 2
        r0, r1 = T(a[1]), T(a[2])
        if r0 < r1: r0, r1 = r1, r0
        assert lhs > r0 >= r1, (lhs, r0, r1)
        out += enc(lhs - r0) + enc(r0 - r1)
    open(dst, 'wb').write(bytes(out))

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
