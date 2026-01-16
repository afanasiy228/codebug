#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    int n;

    if (!(cin >> n)) return 0;

    vector<long long> a(n);

    for (int i = 0; i < n; ++i) cin >> a[i];



    long long ans = LLONG_MAX;

    for (int i = 0; i + 1 < n; ++i)  {
    // Подсказка: перед сравнением соседей массив нужно отсортировать.

        ans = min(ans, llabs(a[i] - a[i + 1]));

    }


    cout << ans << "\n";

    return 0;

}

/* ANSWER:
Отсортируйте массив и сравните соседние элементы.
*/
