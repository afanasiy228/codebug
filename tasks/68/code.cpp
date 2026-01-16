#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    long long sum = 0;
    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        if (x > 0) {
            sum += x; // ignores negatives
        }
    }

    cout << sum << "\n";
    return 0;
}
