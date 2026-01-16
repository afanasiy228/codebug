#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<pair<int,int>> updates(n);
    int maxCoord = 0;
    for (int i = 0; i < n; i++) {
        int x, v;
        cin >> x >> v;
        updates[i] = {x, v};
        maxCoord = max(maxCoord, x);
    }

    vector<long long> arr(maxCoord + 1, 0);
    for (auto [x, v] : updates) {
        arr[x] += v;
    }

    for (int i = 1; i <= maxCoord; i++) {
        arr[i] += arr[i - 1];
    }

    while (q--) {
        int l, r;
        cin >> l >> r;
        if (l < 0) l = 0;
        if (r > maxCoord) r = maxCoord;
        if (l > r) {
            cout << 0 << "
";
        } else {
            long long res = arr[r] - (l > 0 ? arr[l - 1] : 0);
            cout << res << "
";
        }
    }
    return 0;
}
