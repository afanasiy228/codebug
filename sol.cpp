#include <iostream>
using namespace std;

int main() {
    long long n;
    cin >> n;

    int cnt = 0;
    while (n != 0) {
        cnt++;
        n /= 10;
    }
    cout << cnt;
}