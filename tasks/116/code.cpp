#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) {
        return 0;
    }

    int size = 2 * n;
    vector<vector<int>> g(size), rg(size);

    auto id = [&](int lit) {
        int v = abs(lit) - 1;
        if (lit > 0) return 2 * v;
        return 2 * v + 1;
    };

    auto add_edge = [&](int u, int v) {
        g[u].push_back(v);
        rg[v].push_back(u);
    };

    for (int i = 0; i < m; i++) {
        int a, b;
        cin >> a >> b;
        int u = id(a);
        int v = id(b);
        // неверные импликации
        add_edge(u, v);
        add_edge(v, u);
    }

    vector<int> order;
    vector<char> seen(size, false);

    function<void(int)> dfs = [&](int v) {
        seen[v] = true;
        for (int to : g[v]) {
            if (!seen[to]) dfs(to);
        }
        order.push_back(v);
    };

    for (int i = 0; i < size; i++) {
        if (!seen[i]) dfs(i);
    }

    vector<int> comp(size, -1);
    function<void(int, int)> rdfs = [&](int v, int c) {
        comp[v] = c;
        for (int to : rg[v]) {
            if (comp[to] == -1) rdfs(to, c);
        }
    };

    int c = 0;
    for (int i = size - 1; i >= 0; i--) {
        int v = order[i];
        if (comp[v] == -1) {
            rdfs(v, c++);
        }
    }

    vector<int> ans(n, 0);
    for (int i = 0; i < n; i++) {
        if (comp[2 * i] == comp[2 * i + 1]) {
            cout << "NO
";
            return 0;
        }
        ans[i] = comp[2 * i] > comp[2 * i + 1] ? 1 : 0;
    }

    cout << "YES
";
    for (int i = 0; i < n; i++) {
        if (i) cout << ' ';
        cout << ans[i];
    }
    cout << "
";
    return 0;
}
