# Longest path from one flip-flop's Q through combinational cells, from nextpnr's SDF.
# sdfpath.py FILE.sdf FF_INSTANCE
import sys, re, collections
txt = open(sys.argv[1]).read()
start = sys.argv[2]
unesc = lambda s: s.replace('\\', '')
def mx(t): return max(int(x) for x in re.findall(r'-?\d+', t))
inter = collections.defaultdict(list)   # (inst, pin) -> [(inst, pin, delay)]
for m in re.finditer(r'\(INTERCONNECT (\S+) (\S+) (\([^)]*\)) (\([^)]*\))\)', txt):
    s, d = unesc(m.group(1)), unesc(m.group(2))
    si, sp = s.rsplit('/', 1); di, dp = d.rsplit('/', 1)
    inter[(si, sp)].append((di, dp, max(mx(m.group(3)), mx(m.group(4)))))
iopath = collections.defaultdict(list)  # (inst, inpin) -> [(outpin, delay)]
for blk in txt.split('(CELL')[1:]:
    mi = re.search(r'\(INSTANCE ([^)\n]*)\)', blk)
    if not mi: continue
    inst = unesc(mi.group(1).strip())
    for p in re.finditer(r'\(IOPATH (\S+) (\S+) (\([^)]*\)) (\([^)]*\))\)', blk):
        i, o = p.group(1), p.group(2)
        if i in ('CK', 'CLK') or 'CLK' in i: continue
        iopath[(inst, i)].append((o, max(mx(p.group(3)), mx(p.group(4)))))
# nodes are pins; edges: interconnect (driver pin -> sink pin) and IOPATH (cell input ->
# output). Reachable set from the start, then one pass in topological order.
def succ(n):
    inst, pin = n
    out = [((di, dp), d) for di, dp, d in inter.get(n, [])]
    out += [((inst, o), cd) for o, cd in iopath.get(n, [])]
    return out
s0 = (start, 'Q')
seen = {s0}; stack = [s0]; indeg = collections.Counter()
while stack:
    n = stack.pop()
    for m, _ in succ(n):
        indeg[m] += 1
        if m not in seen: seen.add(m); stack.append(m)
best = {s0: 350}; pred = {}
order = [s0]; k = 0
while k < len(order):
    n = order[k]; k += 1
    for m, d in succ(n):
        if best[n] + d > best.get(m, -1): best[m] = best[n] + d; pred[m] = n
        indeg[m] -= 1
        if indeg[m] == 0: order.append(m)
print('pins reached %d, ordered %d (equal: no combinational loop)' % (len(seen), len(order)))
ends = {n: t for n, t in best.items() if not succ(n)}
e = max(ends, key=ends.get)
print('longest arrival from %s/Q: %.3f ns at %s/%s (clk-to-q included, setup not)' % (start, ends[e] / 1000, e[0][:80], e[1]))
n = e
while n in pred:
    print('  %8.3f  %s/%s' % (best[n] / 1000, n[0][:90], n[1])); n = pred[n]
print('endpoint pins reached:', dict(collections.Counter(p for (_, p) in ends)))
left = [n for n in seen if indeg[n] > 0]
print('not ordered (on or after a cycle):', len(left))
for n in left[:15]: print('   ', n[0][:80], n[1], [ (m[0][:50], m[1]) for m,_ in succ(n)][:3])
L = set(left)
# a cycle: walk from an unordered node along successors inside L
n = next(iter(L)); path = []; pos = {}
while n not in pos:
    pos[n] = len(path); path.append(n)
    nxt = [m for m, _ in succ(n) if m in L]
    if not nxt: break
    n = nxt[0]
else:
    print('cycle:'); [print('   ', x[0][:70], x[1]) for x in path[pos[n]:]]
# roots of L: unordered nodes whose unordered predecessors... print in-edges of a few from outside processed
preds = collections.defaultdict(list)
for a in seen:
    for m, _ in succ(a):
        if m in L: preds[m].append(a)
for n in list(L)[:3]:
    print('preds of', n[0][:60], n[1], [(p[0][:50], p[1], p in L) for p in preds[n]][:4])
color = {}
def dfs(u, stk):
    color[u] = 1; stk.append(u)
    for m, _ in succ(u):
        if m not in L: continue
        if color.get(m) == 1:
            i = stk.index(m); print('CYCLE:'); [print('   ', x[0][:70], x[1]) for x in stk[i:]]; return True
        if m not in color and dfs(m, stk): return True
    stk.pop(); color[u] = 2; return False
for u in L:
    if u not in color and dfs(u, []): break
