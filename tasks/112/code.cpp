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

    vector<char> seen(maxVal + 1, 0);
    int cnt = 0;
    for (int v : a) {
        if (!seen[v]) {
            seen[v] = 1;
            cnt++;
        }
    }

    cout << cnt << "
";
    return 0;
}
