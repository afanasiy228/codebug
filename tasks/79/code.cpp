#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<long long> a(n), b(m);
    for (int i = 0; i < n; ++i) cin >> a[i];
    for (int i = 0; i < m; ++i) cin >> b[i];

    vector<long long> out;
    out.reserve(n + m);
    int i = 0, j = 0;
    while (i < n && j < m) {
        if (a[i] < b[j]) {
            out.push_back(a[j]);
            i++;
        } else {
            out.push_back(b[j]);
            j++;
        }
    }
    while (i < n) out.push_back(a[i++]);
    while (j < m) out.push_back(b[j++]);

    for (int k = 0; k < (int)out.size(); ++k) {
        if (k) cout << ' ';
        cout << out[k];
    }
    cout << "\n";
    return 0;
}
