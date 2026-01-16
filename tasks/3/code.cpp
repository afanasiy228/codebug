#include <iostream>
#include <vector>
using namespace std;


int main()  {

    int n;

    cin >> n;


    vector<int> a(n);

    for (int i = 0; i < n; i++) cin >> a[i];


    int l, r;

    cin >> l >> r;


    long long sum = 0;

    for (int i = l; i < r; i++) sum += a[i];
    // TODO: wrong bounds (should include r and 1-based)


    cout << sum;

}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
