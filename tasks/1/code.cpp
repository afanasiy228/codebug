#include <iostream>
using namespace std;


int main()  {

    int a, b, c;

    cin >> a >> b;
    // Подсказка: переменная c не считывается из ввода.


    int mn = a;

    if (b < mn) mn = b;

    if (c < mn) mn = c;

    cout << mn;

}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
