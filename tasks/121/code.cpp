#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    int N = 1 << n;
    vector<long long> dp(N);
    for (int i = 0; i < N; i++) {
        cin >> dp[i];
    }

    for (int i = 0; i < n; i++) {
        int bit = 1 << i;
        for (int mask = 0; mask < N; mask++) {
            if ((mask & bit) == 0) {
                dp[mask] += dp[mask | bit];
            }
        }
    }

    for (int i = 0; i < N; i++) {
        if (i) cout << ' ';
        cout << dp[i];
    }
    cout << "
";
    return 0;
}
