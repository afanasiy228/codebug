#include <bits/stdc++.h>
using namespace std;

vector<vector<int>> g;
vector<long long> dp;

long long dfs(int v) {
    if (dp[v] != -1) return dp[v];
    long long res = 0;
    for (int to : g[v])
        res += dfs(to);
    dp[v] = res;
    return res;
}

int main() {
    int n, m;
    cin >> n >> m;
    g.resize(n);
    for (int i = 0; i < m; i++) {
        int u, v;
        cin >> u >> v;
        g[u - 1].push_back(v - 1);
    }
    dp.assign(n, -1);
    dp[n - 1] = 1;
    cout << dfs(0);
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
