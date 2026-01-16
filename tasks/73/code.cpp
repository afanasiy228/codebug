#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    long long best = LLONG_MIN;
    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        if (i == 0) {
            best = x;
        } else {
            best = x;
        }
        if (i) cout << ' ';
        cout << best;
    }
    cout << "\n";
    return 0;
}
