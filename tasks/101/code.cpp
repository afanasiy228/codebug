#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, k;
    if (!(cin >> n >> k)) {
        return 0;
    }
    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }

    vector<int> res;
    for (int i = 0; i + k <= n; i++) {
        int mx = a[i];
        for (int j = i; j < i + k; j++) {
            mx = max(mx, a[j]);
        }
        res.push_back(mx);
    }

    for (int i = 0; i < (int)res.size(); i++) {
        if (i) cout << ' ';
        cout << res[i];
    }
    cout << "
";
    return 0;
}
