#include <bits/stdc++.h>
using namespace std;

static const int MOD = 1000000007;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    cin >> n >> m;

    unordered_map<int, vector<int>> g;
    g.reserve(n);

    vector<int> indeg(n + 1, 0);

    for (int i = 0; i < m; i++) {
        int u, v;
        cin >> u >> v;
        g[u].push_back(v);
        indeg[v]++;
    }

    queue<int> q;
    for (int i = 1; i <= n; i++) {
        if (indeg[i] == 0)
            q.push(i);
    }

    vector<int> topo;
    topo.reserve(n);

    while (!q.empty()) {
        int v = q.front();
        q.pop();
        topo.push_back(v);
        for (int to : g[v]) {
            if (--indeg[to] == 0)
                q.push(to);
        }
    }

    vector<int> dp(n + 1, 0);
    dp[1] = 1;

    for (int v : topo) {
        for (int to : g[v]) {
            dp[to] += dp[v];
            if (dp[to] >= MOD)
                dp[to] -= MOD;
        }
    }

    for (int i = 1; i <= n; i++) {
        cout << dp[i] << " ";
    }
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
