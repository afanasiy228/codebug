#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    long long S;
    if (!(cin >> n >> S)) {
        return 0;
    }

    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }

    int best = n + 1;
    for (int i = 0; i < n; i++) {
        long long sum = 0;
        for (int j = i; j < n; j++) {
            sum += a[j];
            if (sum >= S) {
                best = min(best, j - i + 1);
                break;
            }
        }
    }

    if (best == n + 1) {
        cout << 0 << "
";
    } else {
        cout << best << "
";
    }
    return 0;
}
