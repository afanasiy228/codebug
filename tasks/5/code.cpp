#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    int n, q;

    if (!(cin >> n >> q)) return 0;

    vector<long long> a(n + 1, 0);

    for (int i = 1; i <= n; ++i)  {

        cin >> a[i];

    }

    vector<long long> pref(n + 1, 0);

    for (int i = 1; i <= n; ++i)  {

        pref[i] = pref[i - 1] + a[i];

    }


    while (q--)  {

        int l, r;

        cin >> l >> r;


        long long ans = pref[r - 1] - pref[l - 1];
        // Подсказка: формула должна брать pref[r], а не pref[r - 1].

        cout << ans << "\n";

    }

    return 0;

}

/* ANSWER:
Используй префиксные суммы, чтобы отвечать на запросы за O(1).
*/
