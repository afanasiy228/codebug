#include <bits/stdc++.h>
using namespace std;

int main() {
    int n, q;
    cin >> n >> q;

    vector<long long> p(n + 1);
    for (int i = 1; i <= n; i++) {
        cin >> p[i];
        p[i] += p[i - 1];
    }

    while (q--) {
        int l, r;
        cin >> l >> r;
        cout << p[r] - p[l] << "
";
    }
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
