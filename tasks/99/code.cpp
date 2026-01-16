#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n; if (!(cin >> n)) return 0;
    vector<vector<int>> g(n);
    for (int i = 0; i < n - 1; ++i) {
        int u, v; cin >> u >> v; --u; --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    int q; cin >> q;

    vector<int> parent(n, 0);
    queue<int> qq; qq.push(0);
    parent[0] = 0;
    while (!qq.empty()) {
        int v = qq.front(); qq.pop();
        for (int to : g[v]) {
            if (to == parent[v]) continue;
            parent[to] = v;
            qq.push(to);
        }
    }

    while (q--) {
        int v, k; cin >> v >> k; --v;
        while (k-- > 0) {
            v = parent[parent[v]]; // skip levels
        }
        cout << v + 1 << "\n";
    }

    return 0;
}
