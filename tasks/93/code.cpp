#include <bits/stdc++.h>
using namespace std;

int n;
vector<vector<int>> g;
vector<long long> w;
long long best;

long long dfs(int v, int p) {
    long long sum = w[v];
    for (int to : g[v]) {
        if (to == p) continue;
        sum = max(sum, w[v] + dfs(to, v));
    }
    best = max(best, sum);
    return sum;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    if (!(cin >> n)) return 0;
    g.assign(n, {});
    for (int i = 0; i < n - 1; ++i) {
        int u, v; cin >> u >> v; --u; --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    w.resize(n);
    for (int i = 0; i < n; ++i) cin >> w[i];

    best = LLONG_MIN;
    dfs(0, -1);
    cout << best << "\n";
    return 0;
}
