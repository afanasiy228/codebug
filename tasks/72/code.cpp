#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long n, m;
    if (!(cin >> n >> m)) {
        return 0;
    }

    long long res = 1 % m;
    for (long long i = 1; i < n; ++i) {
        res = (res * i) % m;
    }

    cout << res << "\n";
    return 0;
}
