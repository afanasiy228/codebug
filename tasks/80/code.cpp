#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];
    long long x; cin >> x;

    int cnt = 0;
    for (int i = 0; i < n; ++i) {
        if (a[i] == x) cnt++;
        if (a[i] > x) break;
    }
    cout << cnt << "\n";
    return 0;
}
