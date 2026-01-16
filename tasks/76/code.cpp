#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    long long best = LLONG_MAX;
    int pos = 0;
    for (int i = 1; i <= n; ++i) {
        long long x;
        cin >> x;
        if (x <= best) {
            best = x;
            pos = i;
        }
    }
    cout << pos << "\n";
    return 0;
}
