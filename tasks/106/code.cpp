#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    if (!(cin >> n >> q)) {
        return 0;
    }

    vector<int> a(n);
    int maxVal = 0;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
        maxVal = max(maxVal, a[i]);
    }

    vector<int> freq(maxVal + 1, 0);
    for (int v : a) {
        freq[v]++;
    }
    for (int i = 1; i <= maxVal; i++) {
        freq[i] += freq[i - 1];
    }

    while (q--) {
        int x;
        cin >> x;
        if (x < 0) {
            cout << 0 << "
";
        } else if (x > maxVal) {
            cout << freq[maxVal] << "
";
        } else {
            cout << freq[x] << "
";
        }
    }
    return 0;
}
