#include <iostream>
#include <string>
#include <algorithm>
using namespace std;


int main()  {

    string a, b;

    cin >> a;
    // Подсказка: для отрицательных чисел нужно игнорировать ведущий '-'.

    b = a;

    reverse(a.begin(), a.end());

    cout << (a == b ? "YES" : "NO");

}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
