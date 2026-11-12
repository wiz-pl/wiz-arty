# check.py ROUTED.json DESIGN.sdf
#
# nextpnr-xilinx's routed netlist (--write) gives each LUT of a fractured pair (A6LUT and
# A5LUT of one site, which share the pins A1-A5) the union of the site's input pins, and
# its SDF (--sdf) has a timing arc from every listed pin to the LUT's output. A LUT then
# appears to read its own output, or two LUTs to read each other: combinational loops
# that the synthesised netlist does not have.
#
# Prints: SDF interconnects that are not routed-netlist connections (expected: 0), the
# LUTs that list their own output as an input, and the pairs of LUTs that list each
# other's outputs, with the site and the LUT's INIT width (2^arity of its function).
import sys, re, json
d = json.load(open(sys.argv[1])); m = list(d['modules'].values())[0]; cells = m['cells']
net = {(k, p): b[0] for k, c in cells.items() for p, b in c['connections'].items() if len(b) == 1}
txt = open(sys.argv[2]).read()
unesc = lambda s: s.replace('\\', '')
total = bad = 0
for e in re.finditer(r'\(INTERCONNECT (\S+) (\S+) ', txt):
    s = tuple(unesc(e.group(1)).rsplit('/', 1)); t = tuple(unesc(e.group(2)).rsplit('/', 1))
    if s[0] in cells and t[0] in cells:
        total += 1
        bad += net.get(s) is None or net.get(s) != net.get(t)
print('SDF interconnects between cells: %d; not in the routed netlist: %d' % (total, bad))
luts = {k: c for k, c in cells.items() if c['type'] == 'SLICE_LUTX'}
def ins(k): return {p: net[(k, p)] for p in luts[k]['connections'] if p.startswith('A') and (k, p) in net}
def outs(k): return {net[(k, p)] for p in ('O5', 'O6') if (k, p) in net}
reader = {}
for k in luts:
    for p, n in ins(k).items(): reader.setdefault(n, set()).add(k)
self_loops = [(k, p) for k in luts for p, n in ins(k).items() if n in outs(k)]
pairs = sorted({tuple(sorted((a, b))) for a in luts for o in outs(a) for b in reader.get(o, ())
                if b != a and outs(b) & set(ins(a).values())})
info = lambda k: '%s INIT=%d bits' % (luts[k]['attributes'].get('NEXTPNR_BEL'), len(luts[k]['parameters'].get('INIT', '')))
print('LUTs listing their own output as an input: %d' % len(self_loops))
for k, p in self_loops[:3]: print('   %s pin %s (%s)' % (k, p, info(k)))
print("pairs of LUTs listing each other's outputs: %d" % len(pairs))
for a, b in pairs[:3]: print('   %s (%s)\n     <-> %s (%s)' % (a, info(a), b, info(b)))
