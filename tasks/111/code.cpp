#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) {
        return 0;
    }

    vector<vector<char>> adj(n + 1, vector<char>(n + 1, 0));
    for (int i = 0; i < m; i++) {
        int u, v;
        cin >> u >> v;
        adj[u][v] = 1;
    }

    const int MOD = 1'000'000'007;
    vector<int> dp(n + 1, 0);
    dp[1] = 1;
    for (int u = 1; u <= n; u++) {
        if (dp[u] == 0) continue;
        for (int v = u + 1; v <= n; v++) {
            if (adj[u][v]) {
                dp[v] += dp[u];
                if (dp[v] >= MOD) dp[v] -= MOD;
            }
        }
    }

    cout << dp[n] << "
";
    return 0;
}
