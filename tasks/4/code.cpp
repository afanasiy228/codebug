#include <iostream>
#include <string>
#include <algorithm>
using namespace std;


int main()  {

    string a, b;

    cin >> a;
    // TODO: should ignore leading '-' for negative numbers

    b = a;

    reverse(a.begin(), a.end());

    cout << (a == b ? "YES" : "NO");

}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
