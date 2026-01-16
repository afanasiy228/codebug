#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    string s;

    long long k;

    if (!(cin >> s >> k)) return 0;

    int n = (int)s.size();

    if (n == 0) return 0;

    k %= n;



    string res = s.substr(k) + s.substr(0, k);
    // TODO: left shift instead of right shift

    cout << res << "\n";

    return 0;

}

/* ANSWER:
Сдвиг вправо: хвост длины k переносим в начало. k можно взять по модулю длины строки.
*/
