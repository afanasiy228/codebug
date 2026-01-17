#include <bits/stdc++.h>
using namespace std;

#define int long long

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    cin >> n >> q;

    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }

    vector<vector<int>> pref(n + 1, vector<int>(n + 1));

    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= n; j++) {
            pref[i][j] = pref[i - 1][j]
                       + pref[i][j - 1]
                       - pref[i - 1][j - 1]
                       + a[(i + j) % n];
        }
    }

    while (q--) {
        int x1, y1, x2, y2;
        cin >> x1 >> y1 >> x2 >> y2;
        cout << pref[x2][y2]
             - pref[x1 - 1][y2]
             - pref[x2][y1 - 1]
             + pref[x1 - 1][y1 - 1] << "
";
    }
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
