#include <bits/stdc++.h>
using namespace std;
long long gcdll(long long a, long long b) { return b ? gcdll(b, a % b) : a; }

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    long long g = 0;
    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        g = gcdll(g, x + 1);
    }
    cout << g << "\n";
    return 0;
}
