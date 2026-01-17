#include <bits/stdc++.h>
using namespace std;

struct SegTree {
    int n;
    vector<long long> t;

    SegTree(const vector<long long>& a) {
        n = (int)a.size();
        t.assign(4 * n, 0);
        build(1, 0, n - 1, a);
    }

    void build(int v, int l, int r, const vector<long long>& a) {
        if (l == r) {
            t[v] = a[l];
        } else {
            int m = (l + r) / 2;
            build(v * 2, l, m, a);
            build(v * 2 + 1, m + 1, r, a);
            t[v] = t[v * 2] + t[v * 2 + 1];
        }
    }

    long long query(int v, int l, int r, int ql, int qr) {
        if (ql > r || qr < l) return 0;
        if (ql <= l && r <= qr) return t[v];
        int m = (l + r) / 2;
        return query(v * 2, l, m, ql, qr) +
               query(v * 2 + 1, m + 1, r, ql, qr);
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    cin >> n >> q;
    vector<long long> a(n);
    for (int i = 0; i < n; i++) cin >> a[i];

    while (q--) {
        int type;
        cin >> type;
        if (type == 1) {
            int l, r;
            cin >> l >> r;
            SegTree st(a);
            cout << st.query(1, 0, n - 1, l, r) << "
";
        } else {
            int i;
            long long x;
            cin >> i >> x;
            a[i] = x;
        }
    }
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
