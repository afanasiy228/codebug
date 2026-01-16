#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) {
        return 0;
    }

    vector<vector<pair<int,int>>> g(n + 1);
    for (int i = 0; i < m; i++) {
        int u, v, w;
        cin >> u >> v >> w;
        g[u].push_back({v, w});
        g[v].push_back({u, w});
    }

    const long long INF = (long long)4e18;
    vector<long long> dist(n + 1, INF);
    vector<char> used(n + 1, false);
    dist[1] = 0;

    for (int iter = 0; iter < n; iter++) {
        int v = -1;
        for (int i = 1; i <= n; i++) {
            if (!used[i] && (v == -1 || dist[i] < dist[v])) {
                v = i;
            }
        }
        if (v == -1 || dist[v] == INF) {
            break;
        }
        used[v] = true;
        for (auto [to, w] : g[v]) {
            if (dist[to] > dist[v] + w) {
                dist[to] = dist[v] + w;
            }
        }
    }

    if (dist[n] == INF) {
        cout << -1 << "
";
    } else {
        cout << dist[n] << "
";
    }
    return 0;
}
