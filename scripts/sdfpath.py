# Longest path from FF/Q to any endpoint pin (forward search; edges that close a cycle are
# skipped, so artefact cycles in the SDF cannot hide a path). Pessimistic: also counts
# interconnect edges nextpnr may attribute to the wrong LUT of a fractured pair.
import sys, re, collections
exec(open(sys.argv[0].replace('sdfpath.py', 'sdfpath_parse.py')).read().split('# nodes are pins')[0])
def succ(n):
    inst, pin = n
    return [((di, dp), d) for di, dp, d in inter.get(n, [])] + [((inst, o), cd) for o, cd in iopath.get(n, [])]
sys.setrecursionlimit(1000000)
memo = {}; onstack = set()
def longest(n):   # longest delay from n to an endpoint
    if n in memo: return memo[n]
    onstack.add(n); best = (0, None)
    for m, d in succ(n):
        if m in onstack: continue
        t = d + longest(m)[0]
        if t > best[0]: best = (t, m)
    onstack.discard(n); memo[n] = best; return best
s0 = (start, 'Q')
t, _ = longest(s0)
print('longest path from %s/Q: %.3f ns + clk-to-q 0.35 = %.3f ns (setup not included)' % (start, t / 1000, t / 1000 + 0.35))
n = s0; acc = 350
while memo.get(n, (0, None))[1] is not None:
    m = memo[n][1]; acc += [d for x, d in succ(n) if x == m][0]; n = m
    print('  %7.3f  %s/%s' % (acc / 1000, n[0][:90], n[1]))
