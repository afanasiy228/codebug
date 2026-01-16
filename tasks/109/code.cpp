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

    vector<int> pos(maxVal + 1, -1);
    for (int i = 0; i < n; i++) {
        if (pos[a[i]] == -1) {
            pos[a[i]] = i + 1;
        }
    }

    while (q--) {
        int x;
        cin >> x;
        if (x < 0 || x > maxVal) {
            cout << -1 << "
";
        } else {
            cout << pos[x] << "
";
        }
    }
    return 0;
}
