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
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }

    vector<int> res(n, -1);
    for (int i = 0; i < n; i++) {
        int ans = -1;
        for (int j = i + 1; j < n; j++) {
            if (a[j] > a[i]) {
                ans = a[j];
                break;
            }
        }
        res[i] = ans;
    }

    for (int i = 0; i < n; i++) {
        if (i) cout << ' ';
        cout << res[i];
    }
    cout << "
";
    return 0;
}
