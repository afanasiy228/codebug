#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) return 0;
    vector<long long> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];

    while (q--) {
        string op; cin >> op;
        if (op == "add") {
            int l, r; long long v;
            cin >> l >> r >> v;
            for (int i = l - 1; i < r; ++i) a[i] += v;
        } else {
            int l, r; cin >> l >> r;
            long long ans = LLONG_MAX;
            for (int i = l - 1; i < r; ++i) {
                ans = min(ans, a[i]);
            }
            cout << ans << "\n";
        }
    }

    return 0;
}
