#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<int> a(n);
    int maxVal = 0;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
        maxVal = max(maxVal, a[i]);
    }

    vector<long long> pref(maxVal + 1, 0);
    for (int v : a) {
        pref[v] += v;
    }
    for (int i = 1; i <= maxVal; i++) {
        pref[i] += pref[i - 1];
    }

    while (q--) {
        int l, r;
        cin >> l >> r;
        if (l < 0) l = 0;
        if (r > maxVal) r = maxVal;
        if (l > r) {
            cout << 0 << "
";
        } else {
            long long res = pref[r] - (l > 0 ? pref[l - 1] : 0);
            cout << res << "
";
        }
    }
    return 0;
}
