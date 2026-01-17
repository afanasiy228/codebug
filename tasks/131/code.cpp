#include <bits/stdc++.h>
using namespace std;

const long long MOD = 1000000007;
const long long P = 91138233;

int main() {
    string s;
    cin >> s;
    int n = (int)s.size();
    vector<long long> h(n + 1), p(n + 1);
    p[0] = 1;
    for (int i = 0; i < n; i++) {
        h[i + 1] = (h[i] * P + s[i]) % MOD;
        p[i + 1] = (p[i] * P) % MOD;
    }
    int l1, r1, l2, r2;
    cin >> l1 >> r1 >> l2 >> r2;

    long long a = (h[r1] - h[l1] * p[r1 - l1]) % MOD;
    long long b = (h[r2] - h[l2] * p[r2 - l2]) % MOD;

    if (a == b)
        cout << "YES";
    else
        cout << "NO";
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
