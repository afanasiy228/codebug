#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    int n;

    if (!(cin >> n)) return 0;

    vector<long long> a(n);

    for (int i = 0; i < n; ++i) cin >> a[i];

    long long x;

    cin >> x;


    int l = 0, r = n - 1, ans = -1;

    while (l <= r)  {

        int mid = (l + r) / 2;

        if (a[mid] >= x)  {
        // TODO: should search last <= x

            ans = mid;

            r = mid - 1;

        }
        else  {

            l = mid + 1;

        }

    }



    cout << (ans == -1 ? 0 : ans + 1) << "\n";

    return 0;

}

/* ANSWER:
Классический бинпоиск по условию a[mid] <= x.
*/
