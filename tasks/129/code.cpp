#include <bits/stdc++.h>
using namespace std;

bool ok(long long x, long long n) {
    return x * x >= n;
}

int main() {
    long long n;
    cin >> n;
    long long l = 0, r = n;
    while (l + 1 < r) {
        long long m = (l + r) / 2;
        if (ok(m, n))
            r = m;
        else
            l = m;
    }
    cout << r;
}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
