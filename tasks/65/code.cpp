#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long n, b;
    if (!(cin >> n >> b)) {
        return 0;
    }

    long long sum = 0;
    while (n > 0) {
        sum += n % 10;
        n /= b;
    }

    cout << sum << "\n";
    return 0;
}
