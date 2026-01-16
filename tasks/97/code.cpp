#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<vector<int>> g(n), rg(n);
    for (int i = 0; i < m; ++i) {
        int u, v; cin >> u >> v; --u; --v;
        g[u].push_back(v);
        g[v].push_back(u); // wrong reverse graph
    }

    vector<int> order;
    vector<int> vis(n, 0);
    function<void(int)> dfs = [&](int v) {
        vis[v] = 1;
        for (int to : g[v]) if (!vis[to]) dfs(to);
        order.push_back(v);
    };
    for (int i = 0; i < n; ++i) if (!vis[i]) dfs(i);

    vector<int> comp(n, -1);
    function<void(int,int)> rdfs = [&](int v, int c) {
        comp[v] = c;
        for (int to : rg[v]) if (comp[to] == -1) rdfs(to, c);
    };

    int cnt = 0;
    for (int i = n - 1; i >= 0; --i) {
        int v = order[i];
        if (comp[v] == -1) {
            rdfs(v, cnt++);
        }
    }

    cout << cnt << "\n";
    return 0;
}
