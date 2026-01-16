#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<vector<int>> g(n);
    for (int i = 0; i < m; ++i) {
        int u, v;
        cin >> u >> v;
        --u; --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }

    vector<int> vis(n, 0);
    int cnt = 0;
    for (int i = 0; i < n; ++i) {
        if (vis[i]) continue;
        cnt++;
        queue<int> q;
        q.push(i);
        vis[i] = 1;
        while (!q.empty()) {
            int v = q.front();
            q.pop();
            for (int to : g[v]) {
                if (!vis[to]) {
                    vis[to] = 1;
                    q.push(to);
                }
            }
        }
        break;
    }

    cout << cnt << "\n";
    return 0;
}
