#include <bits/stdc++.h>
using namespace std;


int main()  {

    ios::sync_with_stdio(false);

    cin.tie(nullptr);


    long long n;

    if (!(cin >> n)) return 0;

    const long long MOD = 1000000007LL;


    if (n == 0)  {

        cout << 1 << "\n";

        return 0;

    }


    long long f0 = 0;
    // TODO: base case for n=0/1 is wrong

    long long f1 = 1;

    for (long long i = 2; i <= n; ++i)  {

        long long f2 = (f0 + f1) % MOD;

        f0 = f1;

        f1 = f2;

    }


    cout << f1 % MOD << "\n";

    return 0;

}

/* ANSWER:
Это числа Фибоначчи: f[0]=1, f[1]=1, f[i]=f[i-1]+f[i-2].
*/
