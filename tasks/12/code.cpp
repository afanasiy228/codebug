#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    string s;

    if (!(cin >> s)) return 0;

    long long sum = 0;



    for (size_t i = 0; i + 1 < s.size(); ++i)  {
    // Подсказка: цикл должен учитывать последний символ.

        sum += s[i] - '0';

    }


    cout << sum << "\n";

    return 0;

}

/* ANSWER:
Можно решать через цикл с n % 10 и n /= 10 или через строку.
*/
