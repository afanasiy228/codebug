#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    vector<vector<int>> g(n);
    for (int i = 0; i < n - 1; ++i) {
        int u, v; cin >> u >> v; --u; --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    int q; cin >> q;

    int LOG = 1;
    while ((1 << LOG) <= n) LOG++;
    vector<vector<int>> up(LOG, vector<int>(n, 0));
    vector<int> depth(n, 0);

    queue<int> qq;
    qq.push(0);
    up[0][0] = 0;
    while (!qq.empty()) {
        int v = qq.front(); qq.pop();
        for (int to : g[v]) {
            if (to == up[0][v]) continue;
            up[0][to] = v;
            depth[to] = depth[v] + 1;
            qq.push(to);
        }
    }
    for (int k = 1; k < LOG; ++k) {
        for (int v = 0; v < n; ++v) {
            up[k][v] = up[k - 1][up[k - 1][v]];
        }
    }

    auto lca = [&](int u, int v) {
        if (depth[u] < depth[v]) swap(u, v);
        int diff = depth[u] - depth[v];
        for (int k = 0; k < LOG; ++k) {
            if (diff & (1 << k)) u = up[k][u];
        }
        if (u == v) return u;
        for (int k = LOG - 1; k >= 0; --k) {
            if (up[k][u] != up[k][v]) {
                u = up[k][u];
                v = up[k][v];
            }
        }
        return up[0][u];
    };

    while (q--) {
        int u, v; cin >> u >> v; --u; --v;
        cout << lca(u, v) + 2 << "\n";
    }
    return 0;
}
