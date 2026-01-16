#include <bits/stdc++.h>
using namespace std;

struct SegTree {
    int n;
    vector<long long> tree;

    SegTree(int n = 0) : n(n), tree(4 * n, 0) {}

    void build(const vector<long long> &a, int v, int l, int r) {
        if (l == r) {
            tree[v] = a[l];
            return;
        }
        int m = (l + r) / 2;
        build(a, v * 2, l, m);
        build(a, v * 2 + 1, m + 1, r);
        tree[v] = tree[v * 2] + tree[v * 2 + 1];
    }

    void update(int v, int l, int r, int pos, long long val) {
        if (l == r) {
            tree[v] = val;
            return;
        }
        int m = (l + r) / 2;
        if (pos <= m) update(v * 2, l, m, pos, val);
        else update(v * 2 + 1, m + 1, r, pos, val);
        tree[v] = tree[v * 2] + tree[v * 2 + 1];
    }

    long long query(int v, int l, int r, int ql, int qr) {
        if (ql > qr) return 0;
        if (ql <= l && r <= qr) return tree[v];
        int m = (l + r) / 2;
        long long res = 0;
        if (ql <= m) res += query(v * 2, l, m, ql, min(qr, m));
        if (qr > m) res += query(v * 2 + 1, m + 1, r, max(ql, m + 1), qr);
        return res;
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<long long> values(n + 1);
    for (int i = 1; i <= n; i++) cin >> values[i];

    vector<vector<int>> g(n + 1);
    for (int i = 0; i < n - 1; i++) {
        int u, v;
        cin >> u >> v;
        g[u].push_back(v);
        g[v].push_back(u);
    }

    vector<int> parent(n + 1, 0), depth(n + 1, 0), heavy(n + 1, -1), sz(n + 1, 0);

    function<int(int, int)> dfs = [&](int v, int p) {
        parent[v] = p;
        sz[v] = 1;
        int max_sub = 0;
        for (int to : g[v]) {
            if (to == p) continue;
            depth[to] = depth[v] + 1;
            int sub = dfs(to, v);
            sz[v] += sub;
            if (sub > max_sub) {
                max_sub = sub;
                heavy[v] = to;
            }
        }
        return sz[v];
    };

    dfs(1, 0);

    vector<int> head(n + 1), pos(n + 1);
    int cur_pos = 0;

    function<void(int, int)> decompose = [&](int v, int h) {
        head[v] = h;
        pos[v] = cur_pos++;
        if (heavy[v] != -1) {
            decompose(heavy[v], h);
        }
        for (int to : g[v]) {
            if (to == parent[v] || to == heavy[v]) continue;
            decompose(to, to);
        }
    };

    decompose(1, 1);

    vector<long long> base(n);
    for (int v = 1; v <= n; v++) {
        base[pos[v]] = values[v];
    }

    SegTree st(n);
    st.build(base, 1, 0, n - 1);

    auto query_path = [&](int a, int b) {
        long long res = 0;
        while (head[a] != head[b]) {
            if (depth[head[a]] < depth[head[b]]) {
                swap(a, b);
            }
            res += st.query(1, 0, n - 1, pos[head[a]], pos[a]);
            a = parent[head[a]];
        }
        // ошибка: не проверяем порядок позиций
        res += st.query(1, 0, n - 1, pos[a], pos[b]);
        return res;
    };

    while (q--) {
        int t;
        cin >> t;
        if (t == 1) {
            int u, v;
            cin >> u >> v;
            cout << query_path(u, v) << "
";
        } else {
            int u;
            long long val;
            cin >> u >> val;
            st.update(1, 0, n - 1, pos[u], val);
        }
    }

    return 0;
}
