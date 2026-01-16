#include <iostream>
using namespace std;


int main()  {

    long long n;

    cin >> n;


    int cnt = 0;

    while (n > 0)  {
    // Подсказка: при n == 0 цикл не выполняется — обработай этот случай.

        cnt++;

        n /= 10;

    }

    cout << cnt;

}

/* ANSWER:
Ответ: см. описание решения в help.md.
*/
