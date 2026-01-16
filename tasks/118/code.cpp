#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<vector<int>> g(n + 1);
    for (int i = 0; i < n - 1; i++) {
        int u, v;
        cin >> u >> v;
        g[u].push_back(v);
        g[v].push_back(u);
    }

    int LOG = 1;
    while ((1 << LOG) <= n) LOG++;

    vector<vector<int>> up(LOG, vector<int>(n + 1));
    vector<int> depth(n + 1, 0);

    queue<int> qu;
    qu.push(1);
    up[0][1] = 1;
    while (!qu.empty()) {
        int v = qu.front();
        qu.pop();
        for (int to : g[v]) {
            if (to == up[0][v]) continue;
            up[0][to] = v;
            depth[to] = depth[v] + 1;
            qu.push(to);
        }
    }

    for (int k = 1; k < LOG; k++) {
        for (int v = 1; v <= n; v++) {
            up[k][v] = up[k - 1][up[k - 1][v]];
        }
    }

    auto lca = [&](int a, int b) {
        if (depth[a] < depth[b]) swap(a, b);
        int diff = depth[a] - depth[b];
        for (int k = LOG - 1; k >= 0; k--) {
            if ((1 << k) < diff) {
                a = up[k][a];
                diff -= 1 << k;
            }
        }
        if (a == b) return a;
        for (int k = LOG - 1; k >= 0; k--) {
            if (up[k][a] != up[k][b]) {
                a = up[k][a];
                b = up[k][b];
            }
        }
        return up[0][a];
    };

    while (q--) {
        int u, v;
        cin >> u >> v;
        int w = lca(u, v);
        int ans = depth[u] + depth[v] - 2 * depth[w];
        cout << ans << "
";
    }
    return 0;
}
