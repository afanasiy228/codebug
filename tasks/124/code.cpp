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

    vector<char> red(n + 1, false);

    while (q--) {
        int type;
        cin >> type;
        if (type == 1) {
            int v;
            cin >> v;
            red[v] = !red[v];
        } else {
            int v, k;
            cin >> v >> k;
            vector<int> dist(n + 1, -1);
            queue<int> qu;
            dist[v] = 0;
            qu.push(v);
            int count = 0;
            while (!qu.empty()) {
                int cur = qu.front();
                qu.pop();
                if (dist[cur] >= k) {
                    continue;
                }
                if (red[cur]) {
                    count++;
                }
                for (int to : g[cur]) {
                    if (dist[to] == -1) {
                        dist[to] = dist[cur] + 1;
                        qu.push(to);
                    }
                }
            }
            cout << count << "
";
        }
    }

    return 0;
}
