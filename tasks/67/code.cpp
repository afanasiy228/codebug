#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    long long best = 0;
    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        best = max(best, x);
    }

    cout << best << "\n";
    return 0;
}
