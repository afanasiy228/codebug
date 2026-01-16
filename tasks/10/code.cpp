#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    long long l, r;

    if (!(cin >> l >> r)) return 0;



    long long x = (l ^ r);
    // Подсказка: XOR l^r не даёт суммарное число единиц на отрезке.

    long long ans = 0;

    while (x > 0)  {

        ans += (x & 1LL);

        x >>= 1;

    }


    cout << ans << "\n";

    return 0;

}

/* ANSWER:
Перебор подходит для небольших ограничений. Для больших можно считать по битам.
*/
