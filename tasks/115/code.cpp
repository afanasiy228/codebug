#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
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

    int bestVal = 0;
    int bestCnt = -1;
    for (int v = 0; v <= maxVal; v++) {
        if (freq[v] > bestCnt) {
            bestCnt = freq[v];
            bestVal = v;
        }
    }

    cout << bestVal << "
";
    return 0;
}
