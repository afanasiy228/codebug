#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    vector<long long> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }

    bool ok = true;
    for (int i = 1; i < n; ++i) {
        if (a[i] < a[i - 1]) {
            ok = false;
        }
    }

    cout << (ok ? "YES\n" : "NO\n");
    return 0;
}
