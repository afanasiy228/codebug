#include <bits/stdc++.h>
using namespace std;

#define int long long

vector<vector<int>> g;
vector<int> tin, tout, flat;
int timer = 0;

void dfs(int v) {
    tin[v] = ++timer;
    flat[timer] = v;
    for (int to : g[v]) {
        dfs(to);
    }
    tout[v] = timer;
}

struct Fenwick {
    int n;
    vector<int> f;
    Fenwick(int n) : n(n), f(n + 1, 0) {}

    void add(int i, int v) {
        for (; i <= n; i += i & -i)
            f[i] += v;
    }

    int sum(int i) {
        int s = 0;
        for (; i > 0; i -= i & -i)
            s += f[i];
        return s;
    }

    int rangeSum(int l, int r) {
        return sum(r) - sum(l - 1);
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    cin >> n >> q;

    vector<int> a(n + 1);
    for (int i = 1; i <= n; i++) cin >> a[i];

    g.resize(n + 1);
    for (int i = 0; i < n - 1; i++) {
        int u, v;
        cin >> u >> v;
        g[u].push_back(v);
    }

    tin.resize(n + 1);
    tout.resize(n + 1);
    flat.resize(n + 1);

    dfs(1);

    Fenwick fw(n);
    for (int i = 1; i <= n; i++) {
        fw.add(tin[i], a[i]);
    }

    while (q--) {
        int type;
        cin >> type;
        if (type == 1) {
            int v;
            cin >> v;
            cout << fw.rangeSum(tin[v], tout[v]) << "
";
        } else {
            int v, x;
            cin >> v >> x;
            fw.add(tin[v], x - a[v]);
            a[v] = x;
        }
    }
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
