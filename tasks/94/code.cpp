#include <bits/stdc++.h>
using namespace std;

struct Edge {
    int to;
    long long cap;
    int rev;
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<vector<Edge>> g(n);

    auto add_edge = [&](int u, int v, long long c) {
        Edge a{v, c, (int)g[v].size()};
        Edge b{u, 0, (int)g[u].size()};
        g[u].push_back(a);
        g[v].push_back(b);
    };

    for (int i = 0; i < m; ++i) {
        int u, v; long long c;
        cin >> u >> v >> c;
        --u; --v;
        add_edge(u, v, c);
    }

    int s, t;
    cin >> s >> t;
    --s; --t;

    long long flow = 0;
    while (true) {
        vector<int> level(n, -1);
        queue<int> q;
        level[s] = 0;
        q.push(s);
        while (!q.empty()) {
            int v = q.front();
            q.pop();
            for (auto &e : g[v]) {
                if (e.cap > 0 && level[e.to] == -1) {
                    level[e.to] = level[v] + 1;
                    q.push(e.to);
                }
            }
        }
        if (level[t] == -1) break;

        vector<int> it(n, 0);
        function<long long(int,long long)> dfs = [&](int v, long long pushed) {
            if (v == t || pushed == 0) return pushed;
            for (int &i = it[v]; i < (int)g[v].size(); ++i) {
                Edge &e = g[v][i];
                if (e.cap > 0 && level[e.to] == level[v] + 1) {
                    long long tr = dfs(e.to, min(pushed, e.cap));
                    if (tr) {
                        e.cap -= tr;
                        // missing reverse update
                        return tr;
                    }
                }
            }
            return 0LL;
        };

        while (true) {
            long long pushed = dfs(s, (long long)4e18);
            if (pushed == 0) break;
            flow += pushed;
        }
    }

    cout << flow << "\n";
    return 0;
}
