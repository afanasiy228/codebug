#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<pair<int,int>> segs(n);
    int maxCoord = 0;
    for (int i = 0; i < n; i++) {
        int l, r;
        cin >> l >> r;
        segs[i] = {l, r};
        maxCoord = max(maxCoord, r);
    }

    vector<int> diff(maxCoord + 2, 0);
    for (auto [l, r] : segs) {
        diff[l] += 1;
        if (r + 1 < (int)diff.size()) {
            diff[r + 1] -= 1;
        }
    }

    for (int i = 1; i < (int)diff.size(); i++) {
        diff[i] += diff[i - 1];
    }

    while (q--) {
        int x;
        cin >> x;
        if (x < 0 || x >= (int)diff.size()) {
            cout << 0 << "
";
        } else {
            cout << diff[x] << "
";
        }
    }
    return 0;
}
