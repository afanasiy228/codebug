#include <bits/stdc++.h>
using namespace std;

int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);

    int n;

    if (!(cin >> n)) return 0;

    vector<long long> a(n);

    for (int i = 0; i < n; ++i) cin >> a[i];

    long long best = 0;

    long long cur = 0;

    for (int i = 0; i < n; ++i)  {

        cur = max(0LL, cur + a[i]);

        best = max(best, cur);

    }

    cout << best << "\n";

    return 0;

}
